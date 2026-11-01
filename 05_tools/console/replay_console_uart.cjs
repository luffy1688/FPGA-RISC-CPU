/* Read actual RTL UART records through the production page JS. No browser claim. */
'use strict';
const fs=require('fs'),path=require('path'),vm=require('vm');
const fixture=fs.readFileSync(path.join(__dirname,'test_console.cjs'),'utf8').split('(async () => {')[0];
const program=fixture+`
(async()=>{
 const log=fs.readFileSync(process.argv[2],'utf8');assert(/CONTEXT_UART_PASS|SEMANTIC_UART_PASS|SEMANTIC_BRANCH_UART_PASS/.test(log));
 await run('connect()');let compact=0,full=0,v3=0;
 for(const line of log.split(/\\r?\\n/)){
  if(!line.startsWith('NR_'))continue;rx(line,'\\n');
  if(line.startsWith('NR_FAST ')){const source=JSON.parse(line.slice(8));if(source[0]===1){assert(text('contextUse').includes('未运行'),text('contextUse'));compact++;continue;}assert([2,3].includes(source[0]));if(source[0]===3){v3++;assert(text('contextHardware').includes('XND'));assert(nodes.get('archNode_xnd').classList.contains('arch-used'));}assert(text('tool').includes('仅语境头'));assert(nodes.get('encoderLogits').children.length===0);assert(!text('processingPath').includes('模型未运行'));assert(text('contextScores').includes(String(source[22])));compact++;}
  if(line.startsWith('NR_RESULT ')){const r=JSON.parse(line.slice(10));if(r.encoder_used===1){if(r.selection_source===5)assert(text('selectionSource').includes('学习语境'));assert(nodes.get('encoderLogits').children.length===6);assert(nodes.get('logits').children.length===6);assert(r.cycles===r.encoder_cycles+r.context_cycles);if(r.context_deny===1)assert(text('resultExplanation').includes('规则不能'));}else if(r.model_used===0){assert(text('contextUse').includes('未运行'),text('contextUse'));assert(nodes.get('logits').children.length===0);}else{assert([2,3].includes(r.model_used));assert(text('contextUse').includes('已运行'));assert(text('encoderUse')==='未运行');if(r.execute===2){assert(text('values').includes('没有有效硬件结果'));assert(!text('values').includes('0.00 °C'));}assert(text('requestCpi')==='—');}full++;}
 }
 assert(compact>=1&&full>=1);assert(writes.length===0,'RX replay must not transmit');await run('disconnect()');
 console.log(JSON.stringify({source:'actual_rtl_uart_through_production_page_js',compact_total:compact,compact_v3:v3,full_json:full,errors:0,browser_verified:false,physical_board_verified:false}));
})().catch(error=>{console.error(error);process.exitCode=1;});
`;
vm.runInNewContext(program,{require,__dirname,__filename,console,Buffer,process,Date},{filename:'console_uart_replay.cjs'});
