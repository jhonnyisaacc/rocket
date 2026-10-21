import { randomBytes, scryptSync, createCipheriv, createDecipheriv } from "node:crypto";
import { generatePrivateKey, privateKeyToAccount } from "viem/accounts";
import { Keypair } from "@solana/web3.js";
import bs58 from "bs58";
import { Secret } from "./redact.js";

export type KeystoreFile = {
  version: 1;
  kdf: "scrypt";
  n: number;
  r: number;
  p: number;
  salt: string;
  iv: string;
  ciphertext: string;
  addresses: { evm: string; solana: string };
};

export type WalletMaterial = {
  evmPrivateKey: Secret;
  evmAddress: string;
  solanaSecretKey: Secret;
  solanaAddress: string;
};

const N = 16384;
const R = 8;
const P = 1;

function keyFromPassphrase(passphrase: string, salt: Buffer): Buffer {
  return scryptSync(passphrase, salt, 32, { N, r: R, p: P });
}

export function createWalletMaterial(): WalletMaterial {
  const evmPrivateKey = generatePrivateKey();
  const account = privateKeyToAccount(evmPrivateKey);
  const solana = Keypair.generate();
  return {
    evmPrivateKey: new Secret(evmPrivateKey),
    evmAddress: account.address,
    solanaSecretKey: new Secret(bs58.encode(solana.secretKey)),
    solanaAddress: solana.publicKey.toBase58(),
  };
}

export function encryptWallet(material: WalletMaterial, passphrase: string): KeystoreFile {
  if (passphrase.length < 12) throw new Error("passphrase must be at least 12 characters");
  const salt = randomBytes(16);
  const iv = randomBytes(12);
  const key = keyFromPassphrase(passphrase, salt);
  const cipher = createCipheriv("aes-256-gcm", key, iv);
  const payload = JSON.stringify({
    evmPrivateKey: material.evmPrivateKey.reveal(),
    solanaSecretKey: material.solanaSecretKey.reveal(),
  });
  const ciphertext = Buffer.concat([cipher.update(payload, "utf8"), cipher.final()]);
  const tag = cipher.getAuthTag();
  return {
    version: 1,
    kdf: "scrypt",
    n: N,
    r: R,
    p: P,
    salt: salt.toString("hex"),
    iv: iv.toString("hex"),
    ciphertext: Buffer.concat([ciphertext, tag]).toString("hex"),
    addresses: { evm: material.evmAddress, solana: material.solanaAddress },
  };
}

export function decryptWallet(file: KeystoreFile, passphrase: string): WalletMaterial {
  const salt = Buffer.from(file.salt, "hex");
  const iv = Buffer.from(file.iv, "hex");
  const blob = Buffer.from(file.ciphertext, "hex");
  const tag = blob.subarray(blob.length - 16);
  const data = blob.subarray(0, blob.length - 16);
  const key = keyFromPassphrase(passphrase, salt);
  const decipher = createDecipheriv("aes-256-gcm", key, iv);
  decipher.setAuthTag(tag);
  const json = Buffer.concat([decipher.update(data), decipher.final()]).toString("utf8");
  const parsed = JSON.parse(json) as { evmPrivateKey: string; solanaSecretKey: string };
  const account = privateKeyToAccount(parsed.evmPrivateKey as `0x${string}`);
  return {
    evmPrivateKey: new Secret(parsed.evmPrivateKey),
    evmAddress: account.address,
    solanaSecretKey: new Secret(parsed.solanaSecretKey),
    solanaAddress: file.addresses.solana,
  };
}

export function keystoreContainsSecret(file: KeystoreFile, material: WalletMaterial): boolean {
  const serialized = JSON.stringify(file);
  return serialized.includes(material.evmPrivateKey.reveal()) || serialized.includes(material.solanaSecretKey.reveal());
}
