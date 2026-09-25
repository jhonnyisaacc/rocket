/* MC-022: one unsigned, read-only Pump buy simulation at a scheduled clock. */
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const root = process.env.MC022_SDK_ROOT || path.join(process.cwd(), 'node_modules');
const sdk = require(path.join(root, '@pump-fun/pump-sdk'));
const web3 = require(path.join(root, '@solana/web3.js'));
const spl = require(path.join(root, '@solana/spl-token'));
const BN = require(path.join(root, 'bn.js'));

const mint = new web3.PublicKey(process.argv[2]);
const out = process.argv[3];
if (!out || fs.existsSync(out)) throw new Error('new output path required');
const user = new web3.PublicKey('HatUYhTtyCHruT9MoYxNKqw3A3wXYP43gsQoFbgqSsFZ');
const rpc = process.env.MC022_RPC || 'https://solana-rpc.publicnode.com';
const spend = new BN('10000000');
const maxSpend = new BN('10100000');
const buybackFeeRecipient = new web3.PublicKey('5YxQFdt3Tr9zJLvkFccqXVUwhdTWJQc1fFg2YPbxvxeD');
const record = {schema:'rocket.memecoin.mc022-unsigned-buy.v1',sdkVersion:'2.0.0',mint:mint.toBase58(),
  user:user.toBase58(),rpc,budgetLamports:spend.toString(),maxSpendLamports:maxSpend.toString(),
  computeLimit:400000,computeUnitPriceMicroLamports:100000,calls:[]};
function save(){fs.writeFileSync(out,JSON.stringify(record,null,2)+'\n');}
async function call(method,params){
  const request={jsonrpc:'2.0',id:record.calls.length+1,method,params};
  const entry={dispatchAt:new Date().toISOString(),request};record.calls.push(entry);save();
  try{
    const response=await fetch(rpc,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(request)});
    const raw=await response.text();entry.receivedAt=new Date().toISOString();entry.httpStatus=response.status;
    entry.rawResponseSha256=crypto.createHash('sha256').update(raw).digest('hex');entry.response=JSON.parse(raw);save();
    if(!response.ok||entry.response.error)throw new Error(`${method}: HTTP ${response.status}: ${JSON.stringify(entry.response.error)}`);
    return entry.response.result;
  }catch(error){entry.error=String(error);entry.receivedAt ||=new Date().toISOString();save();throw error;}
}
function pk(x){return new web3.PublicKey(x);}
function info(raw){return raw&&{data:Buffer.from(raw.data[0],'base64'),lamports:raw.lamports,owner:pk(raw.owner),executable:raw.executable,rentEpoch:raw.rentEpoch};}
function dec(x){return x?.toString(10);}

(async()=>{
  const curveKey=sdk.bondingCurvePda(mint);
  const discovery=await call('getMultipleAccounts',[[mint.toBase58(),curveKey.toBase58()],{encoding:'base64',commitment:'confirmed'}]);
  if(!discovery.value[0]||!discovery.value[1])throw new Error('mint or curve missing at discovery');
  const tokenProgram=pk(discovery.value[0].owner);
  if(!tokenProgram.equals(spl.TOKEN_PROGRAM_ID)&&!tokenProgram.equals(spl.TOKEN_2022_PROGRAM_ID))throw new Error('unsupported base mint owner');
  const userAta=spl.getAssociatedTokenAddressSync(mint,user,true,tokenProgram);
  const addresses=[sdk.GLOBAL_PDA,sdk.PUMP_FEE_CONFIG_PDA,curveKey,mint,userAta,user];
  const bank=await call('getMultipleAccounts',[addresses.map(a=>a.toBase58()),{encoding:'base64',commitment:'confirmed'}]);
  record.bankSlot=bank.context.slot;record.bankAddresses=addresses.map(a=>a.toBase58());save();
  const a=bank.value.map(info);
  for(const i of [0,1,2,3,5])if(!a[i])throw new Error(`required account ${i} absent`);
  if(!a[3].owner.equals(tokenProgram))throw new Error('mint owner changed');
  if(!a[2].owner.equals(sdk.PUMP_PROGRAM_ID))throw new Error('curve owner changed');
  const global=sdk.PUMP_SDK.decodeGlobal(a[0]);
  const feeConfig=sdk.PUMP_SDK.decodeFeeConfig(a[1]);
  const curve=sdk.PUMP_SDK.decodeBondingCurve(a[2]);
  const native=spl.NATIVE_MINT;
  if(curve.isMayhemMode||(!curve.quoteMint.equals(native)&&!curve.quoteMint.equals(web3.PublicKey.default)))
    throw new Error('selected curve no longer native non-Mayhem');
  const mintSupply=new BN(spl.MintLayout.decode(a[3].data).supply.toString());
  const quoted=sdk.getBuyTokenAmountFromSolAmount({global,feeConfig,mintSupply,bondingCurve:curve,
    amount:spend,quoteMint:native});
  const minimum=quoted.muln(99).divn(100);
  record.bankState={curve:curveKey.toBase58(),userLamports:a[5].lamports,userBaseAtaPresent:!!a[4],
    userBaseAmount:a[4]?spl.AccountLayout.decode(a[4].data).amount.toString():null,
    mintSupply:mintSupply.toString(),realTokenReserves:dec(curve.realTokenReserves),
    virtualTokenReserves:dec(curve.virtualTokenReserves),virtualQuoteReserves:dec(curve.virtualQuoteReserves),
    creator:curve.creator.toBase58(),normalFeeRecipient:global.feeRecipient.toBase58(),
    buybackFeeRecipient:buybackFeeRecipient.toBase58()};
  record.quote={quotedBaseAmount:quoted.toString(),requestedBaseAmount:minimum.toString()};save();
  if(minimum.isZero())throw new Error('zero buy amount at bank');
  if(a[5].lamports<15000000)throw new Error('public simulation buyer below funding gate');
  const instructions=[];
  if(!a[4])instructions.push(spl.createAssociatedTokenAccountIdempotentInstruction(user,userAta,user,mint,tokenProgram));
  instructions.push(await sdk.PUMP_SDK.getBuyV2InstructionRaw({user,mint,creator:curve.creator,amount:minimum,
    quoteAmount:maxSpend,feeRecipient:global.feeRecipient,buybackFeeRecipient,tokenProgram,
    quoteMint:native,quoteTokenProgram:spl.TOKEN_PROGRAM_ID}));
  const blockhash=await call('getLatestBlockhash',[{commitment:'confirmed'}]);
  const tx=new web3.Transaction({recentBlockhash:blockhash.value.blockhash,feePayer:user});
  tx.add(web3.ComputeBudgetProgram.setComputeUnitLimit({units:400000}));
  tx.add(web3.ComputeBudgetProgram.setComputeUnitPrice({microLamports:100000}));
  tx.add(...instructions);
  const bytes=tx.serialize({requireAllSignatures:false,verifySignatures:false});
  record.unsignedTransactionBase64=bytes.toString('base64');
  record.unsignedTransactionSha256=crypto.createHash('sha256').update(bytes).digest('hex');
  record.instructions=instructions.map(ix=>({programId:ix.programId.toBase58(),keys:ix.keys.map(k=>({pubkey:k.pubkey.toBase58(),isSigner:k.isSigner,isWritable:k.isWritable})),dataBase64:ix.data.toString('base64')}));save();
  const result=await call('simulateTransaction',[record.unsignedTransactionBase64,
    {encoding:'base64',sigVerify:false,replaceRecentBlockhash:true,commitment:'confirmed',innerInstructions:true,
      accounts:{encoding:'base64',addresses:[user.toBase58(),userAta.toBase58(),curveKey.toBase58()]}}]);
  record.simulationSummary={contextSlot:result.context?.slot,err:result.value?.err,
    unitsConsumed:result.value?.unitsConsumed,fee:result.value?.fee};save();
  console.log(JSON.stringify({mint:mint.toBase58(),bankSlot:record.bankSlot,
    requestedBaseAmount:minimum.toString(),simulation:record.simulationSummary}));
})().catch(error=>{record.fatalError=String(error);save();console.error(error);process.exitCode=1;});
