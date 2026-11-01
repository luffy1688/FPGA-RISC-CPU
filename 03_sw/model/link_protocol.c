/* Bounded single-command RPC envelope, implemented for this project.
 * Framing/sequence/FCS concepts follow common embedded RPC practice (e.g.
 * Apache-2.0 Google Pigweed pw_hdlc); this CRC16 protocol is not HDLC-compatible.
 * Transport CRC is error detection, not authentication or an execution policy. */
#include "link_protocol.h"
#include "../platform/needle_platform.h"
static uint32_t seen,last_sequence;
static int skip_lf;
static uint16_t crc_byte(uint16_t crc,uint8_t c) {
    uint32_t i;crc^=(uint16_t)c<<8;
    for(i=0;i<8;i++)crc=(uint16_t)((crc&0x8000u)?((uint32_t)crc<<1)^0x1021u:(uint32_t)crc<<1);
    return crc;
}
/* RFC3629 scalar UTF-8, plus the text transport's no-NUL contract.
 * Reject before the model and before accepting a framed sequence number. */
int nr_link_utf8_valid(const uint8_t *b,uint32_t n) {
    uint32_t i=0,j,more;uint8_t a,lo,hi;
    while(i<n) {
        a=b[i++];if(!a)return 0;if(a<0x80u)continue;
        lo=0x80u;hi=0xbfu;
        if(a>=0xc2u && a<=0xdfu)more=1;
        else if(a>=0xe0u && a<=0xefu){more=2;if(a==0xe0u)lo=0xa0u;if(a==0xedu)hi=0x9fu;}
        else if(a>=0xf0u && a<=0xf4u){more=3;if(a==0xf0u)lo=0x90u;if(a==0xf4u)hi=0x8fu;}
        else return 0;
        if(n-i<more || b[i]<lo || b[i]>hi)return 0;
        for(j=1;j<more;j++)if(b[i+j]<0x80u || b[i+j]>0xbfu)return 0;
        i+=more;
    }
    return 1;
}
static uint8_t get_byte(void) {
    while(!(NR_MMIO(0x1000000cu)&2u)){}
    return (uint8_t)NR_MMIO(0x10000010u);
}
static int timed_byte(uint32_t end,uint8_t *out) {
    while(!(NR_MMIO(0x1000000cu)&2u))if((int32_t)(nr_cycle()-end)>=0)return 0;
    *out=(uint8_t)NR_MMIO(0x10000010u);return 1;
}
static void discard_bad_frame(uint32_t end) {uint8_t c;while(timed_byte(end,&c)){};}
uint32_t nr_link_seen(void){return seen;}
uint32_t nr_link_sequence(void){return last_sequence;}
int nr_link_read(uint8_t *buffer,uint32_t capacity,nr_link_request_t *meta) {
    uint8_t first;uint32_t n=0;int overflow=0;
    meta->framed=0;meta->sequence=0;
    do {first=get_byte();if(skip_lf){skip_lf=0;if(first=='\n')continue;}break;}while(1);
    if(first==0xa5u) {
        uint8_t header[10],c,lo,hi;uint32_t i,length,seq,end=nr_cycle()+NR_PLATFORM_CLOCK_HZ/10u;
        uint16_t crc=crc_byte(0xffffu,first);header[0]=first;
        for(i=1;i<10;i++){if(!timed_byte(end,&header[i]))return NR_INPUT_TIMEOUT;crc=crc_byte(crc,header[i]);}
        length=(uint32_t)header[4]|(uint32_t)header[5]<<8;
        if(header[1]!=0x5au||header[2]!=1||header[3]!=0x10u||!length||length>capacity) {
            discard_bad_frame(end);return NR_INPUT_FRAME;
        }
        for(i=0;i<length;i++) {
            if(!timed_byte(end,&c))return NR_INPUT_TIMEOUT;
            buffer[i]=c;crc=crc_byte(crc,c);
        }
        if(!timed_byte(end,&lo)||!timed_byte(end,&hi))return NR_INPUT_TIMEOUT;
        if(crc!=((uint16_t)lo|((uint16_t)hi<<8)))return NR_INPUT_CRC;
        seq=(uint32_t)header[6]|(uint32_t)header[7]<<8|(uint32_t)header[8]<<16|(uint32_t)header[9]<<24;
        if(seen&&(int32_t)(seq-last_sequence)<=0)return NR_INPUT_SEQUENCE;
        for(i=0;i<length;i++)if(buffer[i]=='\n'||buffer[i]=='\r'||buffer[i]==0)return NR_INPUT_FRAME;
        if(!nr_link_utf8_valid(buffer,length))return NR_INPUT_UTF8;
        seen=1;last_sequence=seq;meta->framed=1;meta->sequence=seq;
        return (int)length;
    }
    for(;;) {
        uint8_t c=first;
        if(c=='\r'||c=='\n'){skip_lf=c=='\r';return overflow?NR_INPUT_TOO_LONG:!nr_link_utf8_valid(buffer,n)?NR_INPUT_UTF8:(int)n;}
        if(c==8||c==127){if(n&&!overflow)n--;}
        else if(n<capacity)buffer[n++]=c;else overflow=1;
        first=get_byte();
    }
}
static void put32(uint8_t *b,uint32_t value) {uint32_t i;for(i=0;i<4;i++)b[i]=(uint8_t)(value>>(8*i));}
void nr_link_result(uint32_t id,uint32_t config,const nr_tool_request_t *r,nr_exec_status_t execution,
 uint32_t value,uint32_t decision,uint32_t tool_cycles,uint32_t request_cycles,
 const nr_tool_receipt_t *receipt,uint32_t sequence,uint32_t model_used,uint32_t context_used,uint32_t context_deny,uint32_t context_xnd_used) {
    uint8_t b[64];uint32_t i;uint16_t crc=0xffffu;
    b[0]=0xa5;b[1]=0x5a;b[2]=1;b[3]=0x21;b[4]=52;b[5]=0;put32(b+6,sequence);
    put32(b+10,id);b[14]=(uint8_t)config;b[15]=(uint8_t)r->tool;b[16]=(uint8_t)r->status;
    b[17]=(uint8_t)(r->operation|r->selection_source<<2);b[18]=(uint8_t)execution;b[19]=(uint8_t)receipt->kind;
    b[20]=(uint8_t)(0x80u|(receipt->match&1u)|((receipt->enabled&1u)<<1)|((context_used&1u)<<2)|((context_deny&1u)<<3)|((context_xnd_used&1u)<<4));b[21]=(uint8_t)model_used;
    put32(b+22,(uint32_t)r->argument);put32(b+26,value);put32(b+30,decision);
    put32(b+34,tool_cycles);put32(b+38,request_cycles);put32(b+42,receipt->requested);
    put32(b+46,receipt->readback);put32(b+50,receipt->period);put32(b+54,receipt->high);
    put32(b+58,NR_MMIO(0x1000000cu));
    for(i=0;i<62;i++){crc=crc_byte(crc,b[i]);}
    b[62]=(uint8_t)crc;b[63]=(uint8_t)(crc>>8);
    for(i=0;i<64;i++)nr_putc((char)b[i]);
}
