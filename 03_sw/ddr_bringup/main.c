/* DDR数据窗最小集成固件。不是模型全网DDR版，也不测试真实PHY带宽。
 * 每个检查都由真正的RV32指令执行；XND读取/写出DDR数据而非主机代算。
 * GPIO阶段字节是TB可观察契约，代码和栈始终在BRAM。 */
#include <stdint.h>
#include "../xnd_runtime/xnd_mmio.h"
#define REG32(a) (*(volatile uint32_t *)(uintptr_t)(a))
#define GPIO REG32(0x10000004u)
#define DDR_STATE REG32(0x1000010cu)
#define DDR_BASE 0x80000000u
#define CPU_TEST (DDR_BASE+0x1000u)
#define A_ADDR (DDR_BASE+0x2000u)
#define W4_ADDR (DDR_BASE+0x2100u)
#define Y4_ADDR (DDR_BASE+0x2200u)
#define W8_ADDR (DDR_BASE+0x2300u)
#define Y8_ADDR (DDR_BASE+0x2400u)
#define COLS 16u
#define ROWS 3u
#define POLLS 100000u
#define GUARD 0x9facbeefu
#define DDR_LIMIT (DDR_BASE+0x00100000u)
#define DDR_OOB DDR_LIMIT
#define MMIO_HOLE 0x10000110u

/* Startup trap handler consumes the two intentional access faults below.
 * Keeping the counters in firmware makes the negative test observable on
 * GPIO/TB without changing the CPU or DDR bridge. */
volatile uint32_t ddr_expected_traps;
volatile uint32_t ddr_observed_traps;

static const int8_t activation[COLS]={-3,7,-8,2,0,1,-1,5,3,-4,6,-2,4,1,-5,2};
static void finish(uint32_t marker) {
    GPIO=marker;
    for(;;) __asm__ volatile("nop");
}
static void check(int ok,uint32_t failure) {
    if(!ok) finish(failure);
}
static int8_t w4(uint32_t row,uint32_t col) {
    return (int8_t)((int32_t)((row*3u+col)%16u)-8);
}
static int8_t w8(uint32_t row,uint32_t col) {
    return (int8_t)((int32_t)((row*7u+col)%11u)-5);
}
static int8_t alternate(uint32_t col) {
    return (int8_t)((int32_t)((col*5u)%13u)-6);
}
static int32_t golden(uint32_t row,int int4) {
    int32_t result=0;
    for(uint32_t col=0;col<COLS;col++)
        result+=(int32_t)(int4?activation[col]:alternate(col)) *
                (int32_t)(int4?w4(row,col):w8(row,col));
    return result;
}
static void cpu_data_test(void) {
    volatile uint32_t *words=(volatile uint32_t *)(uintptr_t)CPU_TEST;
    volatile uint8_t *bytes=(volatile uint8_t *)(uintptr_t)CPU_TEST;
    volatile uint16_t *half=(volatile uint16_t *)(uintptr_t)CPU_TEST;
    uint32_t expected[16];
    /* 16 words cover every lane of two consecutive 256-bit native beats. */
    for(uint32_t i=0;i<16;i++) {
        expected[i]=0x10203040u^((i+1u)*0x01010101u);
        words[i]=expected[i];
    }
    /* The final aligned DDR word is still inside the one-megabyte window. */
    REG32(DDR_LIMIT-4u)=0x13579bdfu;
    check(REG32(DDR_LIMIT-4u)==0x13579bdfu,0xe1u);
    for(uint32_t i=0;i<16;i++) check(words[i]==expected[i],0xe1u);
    /* Byte strobes span byte31/32, preserving all the other byte lanes. */
    for(uint32_t i=0;i<48;i++) {
        uint32_t index=i+3u,shift=(index&3u)*8u,value=(0x51u+i)&255u;
        bytes[index]=(uint8_t)value;
        expected[index/4u]=(expected[index/4u]&~(255u<<shift))|(value<<shift);
    }
    for(uint32_t i=0;i<16;i++) check(words[i]==expected[i],0xe2u);
    half[0]=0xbeefu;half[15]=0xa55au;half[16]=0x6c3du;
    expected[0]=(expected[0]&0xffff0000u)|0xbeefu;
    expected[7]=(expected[7]&0x0000ffffu)|0xa55a0000u;
    expected[8]=(expected[8]&0xffff0000u)|0x6c3du;
    for(uint32_t i=0;i<16;i++) check(words[i]==expected[i],0xe3u);
    check(half[0]==0xbeefu && half[15]==0xa55au && half[16]==0x6c3du,0xe3u);
    check((int32_t)((volatile int16_t *)(uintptr_t)CPU_TEST)[0]==-16657,0xe3u);
    GPIO=0x20u;
}
static void reject_window_and_mmio_hole(void) {
    volatile uint32_t sink;
    /* DDR_BASE..DDR_LIMIT is inclusive only up to LIMIT-4.  A CPU read at
     * LIMIT must take the normal load-access-fault path and never reach HMIC. */
    ddr_expected_traps=2u;
    ddr_observed_traps=0u;
    sink=REG32(DDR_OOB);
    (void)sink;
    /* 0x10000110 is outside the implemented peripheral map [..0x10f]. */
    sink=REG32(MMIO_HOLE);
    (void)sink;
    check(ddr_expected_traps==0u && ddr_observed_traps==2u,0xf0u);
    GPIO=0x22u;
}

static void initialize_matrices(void) {
    volatile int8_t *a=(volatile int8_t *)(uintptr_t)A_ADDR;
    volatile uint8_t *packed=(volatile uint8_t *)(uintptr_t)W4_ADDR;
    volatile int8_t *weights8=(volatile int8_t *)(uintptr_t)W8_ADDR;
    volatile uint32_t *y4=(volatile uint32_t *)(uintptr_t)Y4_ADDR;
    volatile uint32_t *y8=(volatile uint32_t *)(uintptr_t)Y8_ADDR;
    for(uint32_t col=0;col<COLS;col++) a[col]=activation[col];
    for(uint32_t row=0;row<ROWS;row++) {
        for(uint32_t col=0;col<COLS;col+=2)
            packed[row*(COLS/2)+col/2]=((uint8_t)w4(row,col)&15u)|
                                      (((uint8_t)w4(row,col+1)&15u)<<4);
        for(uint32_t col=0;col<COLS;col++) weights8[row*COLS+col]=w8(row,col);
        y4[row]=0x77777777u;y8[row]=0x77777777u;
    }
    y4[ROWS]=GUARD;y8[ROWS]=GUARD;
    xnd_fence();
}
static void load(const xnd_job_t *job,uint32_t failure,int concurrent_cpu) {
    xnd_ack();check(xnd_load_activation(job)==XND_OK,failure);
    /* These unrelated CPU DDR operations run while the activation LOAD is
     * outstanding, exercising CPU/XND arbitration in the shared data window. */
    if(concurrent_cpu) {
        REG32(CPU_TEST+0x80u)=0x55aa7711u;
        check(REG32(CPU_TEST+0x80u)==0x55aa7711u,failure);
    }
    check(xnd_wait(POLLS)==XND_OK,failure);
    check((XND_STATUS&XND_SLOT_VALID(job->slot))!=0u,failure);
    check(XND_DMA_READ_BYTES==COLS && XND_DMA_WRITE_BYTES==0u,failure);
}
static void gemv(const xnd_job_t *job,int int4,uint32_t failure) {
    xnd_ack();check(xnd_launch_gemv(job)==XND_OK,failure);
    check(xnd_wait(POLLS)==XND_OK,failure);
    check((XND_STATUS&(XND_BUSY_MASK|XND_ERROR_MASK))==0u,failure);
    volatile int32_t *y=(volatile int32_t *)(uintptr_t)job->output_addr;
    for(uint32_t row=0;row<ROWS;row++) check(y[row]==golden(row,int4),failure);
    check((uint32_t)y[ROWS]==GUARD,failure);
    check(XND_MACS==ROWS*COLS && XND_DMA_WRITE_BYTES==ROWS*4u,failure);
    check(XND_DMA_READ_BYTES==ROWS*job->weight_stride_bytes,failure);
}
int main(void) {
    GPIO=0x10u;
    uint32_t polls=POLLS;
    while(polls-- && !(DDR_STATE&1u)) { }
    check((DDR_STATE&3u)==1u,0xe0u);
    cpu_data_test();reject_window_and_mmio_hole();initialize_matrices();
    xnd_job_t job={A_ADDR,W4_ADDR,Y4_ADDR,COLS,ROWS,COLS/2u,XND_CTRL_INT4,0};
    load(&job,0xe4u,1);
    /* The vector is now resident. Changing its DDR source must NOT change
     * slot0 computation; this proves LOAD/GEMV semantics across the DDR path. */
    for(uint32_t col=0;col<COLS;col++) ((volatile int8_t *)(uintptr_t)A_ADDR)[col]=99;
    gemv(&job,1,0xe5u);
    /* Reuse slot0, without a second LOAD, against the same DDR matrix. */
    gemv(&job,1,0xe6u);GPIO=0x30u;
    for(uint32_t col=0;col<COLS;col++) ((volatile int8_t *)(uintptr_t)A_ADDR)[col]=alternate(col);
    job.weight_addr=W8_ADDR;job.output_addr=Y8_ADDR;
    job.weight_stride_bytes=COLS;job.control=0;job.slot=1;
    load(&job,0xe7u,1);gemv(&job,0,0xe8u);GPIO=0x40u;
    check((XND_STATUS&(XND_SLOT_VALID(0)|XND_SLOT_VALID(1)))==
          (XND_SLOT_VALID(0)|XND_SLOT_VALID(1)),0xe9u);
    xnd_ack();check((XND_STATUS&(XND_DONE_MASK|XND_ERROR_MASK))==0u,0xe9u);
#ifndef NR_DDR_FAULT_TEST
    finish(0xa5u);
#else
    /* TB observes D1 and drops the next HMIC read response. The bridge fault
     * is sticky. We inspect/ack XND locally, then stop; only common reset can
     * restore DDR. We deliberately do not start another DDR job after fault. */
    GPIO=0xa5u;GPIO=0xd1u;
    check(xnd_load_activation(&job)==XND_OK,0xeau);
    int status=xnd_wait(POLLS);
    check(status==XND_DMA_FAULT || status==XND_DMA_TIMEOUT,0xebu);
    check((XND_STATUS&(XND_BUSY_MASK|XND_DONE_MASK|XND_ERROR_MASK))==
          (XND_DONE_MASK|XND_ERROR_MASK),0xebu);
    check((DDR_STATE&3u)==2u,0xecu);
    xnd_ack();check((XND_STATUS&(XND_DONE_MASK|XND_ERROR_MASK))==0u,0xedu);
    finish(0xa6u);
#endif
    return 0;
}
