import { chmodSync, writeFileSync } from "node:fs";
import { createWalletMaterial, encryptWallet, keystoreContainsSecret } from "./keystore.js";

function main(): void {
  const passphrase = process.env.KEYSTORE_PASSPHRASE ?? "";
  const outPath = process.env.KEYSTORE_PATH ?? "wallet.keystore.json";
  if (passphrase.length < 12) {
    console.error("Set KEYSTORE_PASSPHRASE to at least 12 characters. The key is not printed.");
    process.exit(2);
  }
  const material = createWalletMaterial();
  const file = encryptWallet(material, passphrase);
  if (keystoreContainsSecret(file, material)) {
    console.error("Refusing to write a keystore that contains a raw key.");
    process.exit(1);
  }
  writeFileSync(outPath, `${JSON.stringify(file, null, 2)}\n`, { mode: 0o600 });
  chmodSync(outPath, 0o600);
  console.log(JSON.stringify({ path: outPath, evmAddress: file.addresses.evm, solanaAddress: file.addresses.solana }));
}

const entry = process.argv[1] ?? "";
if (entry.endsWith("create-wallet.js")) main();
