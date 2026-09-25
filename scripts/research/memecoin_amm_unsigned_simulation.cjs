/* MC-021: bounded, read-only inventory-backed PumpSwap sell simulation. */
const fs = require('node:fs');
const crypto = require('node:crypto');
const path = require('node:path');

const root = process.env.MC021_SDK_ROOT || path.join(process.cwd(), 'node_modules');
const sdk = require(path.join(root, '@pump-fun/pump-swap-sdk'));
const web3 = require(path.join(root, '@solana/web3.js'));
const spl = require(path.join(root, '@solana/spl-token'));
const BN = require(path.join(root, 'bn.js'));

const rpc = process.env.MC021_RPC || 'https://solana-rpc.publicnode.com';
const out = process.argv[2];
if (!out || fs.existsSync(out)) throw new Error('new output path required');
const poolKey = new web3.PublicKey('7LgDUm7jmZ2TQc7GBzVuGSBPscWGtph4sQXrKZZ22ztg');
const user = new web3.PublicKey('HatUYhTtyCHruT9MoYxNKqw3A3wXYP43gsQoFbgqSsFZ');
const userBaseTokenAccount = new web3.PublicKey('DPbw3QZfpKDba4T9n5be5nfjEjjrZT82MFVGnq4rsMeW');
const base = new BN('10000000000');
const record = {schema:'rocket.memecoin.mc021-unsigned-simulation.v1', sdkVersion:'1.20.0', rpc,
  pool:poolKey.toBase58(), user:user.toBase58(), userBaseTokenAccount:userBaseTokenAccount.toBase58(),
  baseAmount:base.toString(), slippagePercent:1, computeLimit:400000, computeUnitPriceMicroLamports:100000,
  calls:[]};
function save() { fs.writeFileSync(out, JSON.stringify(record, null, 2)+'\n'); }
async function call(method, params) {
  const request={jsonrpc:'2.0',id:record.calls.length+1,method,params};
  const entry={dispatchAt:new Date().toISOString(),request}; record.calls.push(entry); save();
  try {
    const response=await fetch(rpc,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(request)});
    entry.receivedAt=new Date().toISOString(); entry.httpStatus=response.status;
    const raw=await response.text(); entry.rawResponseSha256=crypto.createHash('sha256').update(raw).digest('hex');
    entry.response=JSON.parse(raw); save();
    if (!response.ok || entry.response.error) throw new Error(`${method}: HTTP ${response.status}: ${JSON.stringify(entry.response.error)}`);
    return entry.response.result;
  } catch (error) { entry.error=String(error); entry.receivedAt ||= new Date().toISOString();save();throw error; }
}
function pk(x) {return new web3.PublicKey(x);}
function info(raw) {return raw&&{data:Buffer.from(raw.data[0],'base64'),lamports:raw.lamports,owner:pk(raw.owner),executable:raw.executable,rentEpoch:raw.rentEpoch};}
function bnObject(value) {return Object.fromEntries(Object.entries(value).map(([k,v])=>[k,BN.isBN(v)?v.toString(10):v]));}

(async()=>{
  const first=await call('getAccountInfo',[poolKey.toBase58(),{encoding:'base64',commitment:'confirmed'}]);
  if (!first.value) throw new Error('pool absent');
  const preliminary=sdk.PUMP_AMM_SDK.decodePool(info(first.value));
  const baseMint=preliminary.baseMint, quoteMint=preliminary.quoteMint;
  const baseMintFirst=await call('getAccountInfo',[baseMint.toBase58(),{encoding:'base64',commitment:'confirmed'}]);
  if (!baseMintFirst.value) throw new Error('base mint absent');
  const baseTokenProgram=pk(baseMintFirst.value.owner);
  const quoteMintFirst=await call('getAccountInfo',[quoteMint.toBase58(),{encoding:'base64',commitment:'confirmed'}]);
  if (!quoteMintFirst.value) throw new Error('quote mint absent');
  const quoteTokenProgram=pk(quoteMintFirst.value.owner);
  const userQuoteTokenAccount=spl.getAssociatedTokenAddressSync(quoteMint,user,true,quoteTokenProgram);
  const addresses=[sdk.GLOBAL_CONFIG_PDA,sdk.PUMP_AMM_FEE_CONFIG_PDA,poolKey,baseMint,quoteMint,
    preliminary.poolBaseTokenAccount,preliminary.poolQuoteTokenAccount,userBaseTokenAccount,userQuoteTokenAccount,user];
  const bank=await call('getMultipleAccounts',[addresses.map(a=>a.toBase58()),{encoding:'base64',commitment:'confirmed'}]);
  record.bankSlot=bank.context.slot;record.bankAddresses=addresses.map(a=>a.toBase58());save();
  const a=bank.value.map(info);
  for(const i of [0,1,2,3,4,5,6,7]) if(!a[i]) throw new Error(`required account absent at bank index ${i}`);
  const globalConfig=sdk.PUMP_AMM_SDK.decodeGlobalConfig(a[0]);
  const feeConfig=sdk.PUMP_AMM_SDK.decodeFeeConfig(a[1]);
  const pool=sdk.PUMP_AMM_SDK.decodePool(a[2]);
  if(!pool.baseMint.equals(baseMint)||!pool.quoteMint.equals(quoteMint)||
    !pool.poolBaseTokenAccount.equals(addresses[5])||!pool.poolQuoteTokenAccount.equals(addresses[6]))
    throw new Error('pool changed between address discovery and bank read');
  const poolBaseAmount=new BN(spl.AccountLayout.decode(a[5].data).amount.toString());
  const poolQuoteAmount=new BN(spl.AccountLayout.decode(a[6].data).amount.toString());
  const userAmount=new BN(spl.AccountLayout.decode(a[7].data).amount.toString());
  const tokenOwner=new web3.PublicKey(spl.AccountLayout.decode(a[7].data).owner);
  if(!tokenOwner.equals(user)||userAmount.lt(base))throw new Error('holder account lost required inventory');
  const state={globalConfig,feeConfig,poolKey,poolAccountInfo:a[2],pool,poolBaseAmount,poolQuoteAmount,
    baseTokenProgram,quoteTokenProgram,baseMint,baseMintAccount:spl.MintLayout.decode(a[3].data),
    user,userBaseTokenAccount,userQuoteTokenAccount,userBaseAccountInfo:a[7],userQuoteAccountInfo:a[8]};
  const quote=sdk.sellBaseInput({base,slippage:1,baseReserve:poolBaseAmount,quoteReserve:poolQuoteAmount,
    virtualQuoteReserves:pool.virtualQuoteReserves,globalConfig,baseMintAccount:state.baseMintAccount,
    baseMint,coinCreator:pool.coinCreator,creator:pool.creator,feeConfig,quoteMint,
    isMayhemMode:pool.isMayhemMode,creatorFeeBps:pool.creatorFeeBps});
  record.bankState={userBaseAmount:userAmount.toString(),userLamports:a[9]?.lamports ?? null,poolBaseAmount:poolBaseAmount.toString(),
    poolQuoteAmount:poolQuoteAmount.toString(),virtualQuoteReserves:pool.virtualQuoteReserves.toString(),
    quoteMint:quoteMint.toBase58(),userQuoteAccountPresent:!!a[8]};
  record.sdkQuote=bnObject(quote);save();
  const instructions=await sdk.PUMP_AMM_SDK.sellInstructions(state,base,quote.minQuote);
  const blockhash=await call('getLatestBlockhash',[{commitment:'confirmed'}]);
  const tx=new web3.Transaction({recentBlockhash:blockhash.value.blockhash,feePayer:user});
  tx.add(web3.ComputeBudgetProgram.setComputeUnitLimit({units:400000}));
  tx.add(web3.ComputeBudgetProgram.setComputeUnitPrice({microLamports:100000}));
  tx.add(...instructions);
  const serialized=tx.serialize({requireAllSignatures:false,verifySignatures:false});
  record.unsignedTransactionBase64=serialized.toString('base64');
  record.unsignedTransactionSha256=crypto.createHash('sha256').update(serialized).digest('hex');
  record.instructions=instructions.map(ix=>({programId:ix.programId.toBase58(),keys:ix.keys.map(k=>({pubkey:k.pubkey.toBase58(),isSigner:k.isSigner,isWritable:k.isWritable})),dataBase64:ix.data.toString('base64')}));save();
  const result=await call('simulateTransaction',[record.unsignedTransactionBase64,
    {encoding:'base64',sigVerify:false,replaceRecentBlockhash:true,commitment:'confirmed',innerInstructions:true,
      accounts:{encoding:'base64',addresses:[userBaseTokenAccount.toBase58(),userQuoteTokenAccount.toBase58(),
        pool.poolBaseTokenAccount.toBase58(),pool.poolQuoteTokenAccount.toBase58(),user.toBase58()]}}]);
  record.simulationSummary={contextSlot:result.context?.slot,err:result.value?.err,unitsConsumed:result.value?.unitsConsumed,
    returnData:result.value?.returnData};save();
  console.log(JSON.stringify({bankSlot:record.bankSlot,quote:record.sdkQuote,simulation:record.simulationSummary},null,2));
})().catch(error=>{record.fatalError=String(error);save();console.error(error);process.exitCode=1;});
