#ifndef NEEDLERV_XND_MMIO_H
#define NEEDLERV_XND_MMIO_H
#include <stdint.h>

/*
 * XND = our custom low-bit execution unit, not the upstream Needle runtime.
 * Register offset is the byte distance from XND_BASE.
 * Activation/output MUST live in uncached AI RAM [0x20000, 0x80000).
 * Read-only weights may reside anywhere in physical RAM [0, 0x80000).
 */
#define XND_BASE             0x40000000u
#define XND_AI_RAM_START     0x00020000u
#define XND_AI_RAM_END       0x00080000u
#if XND_BASE != 0x40000000u || XND_AI_RAM_START != 0x00020000u || XND_AI_RAM_END != 0x00080000u
#error Experimental SRAM expansion must not move XND MMIO or cached CPU boundary
#endif
#define XND_REG(off)         (*(volatile uint32_t *)(XND_BASE+(off)))
#define XND_STATUS           XND_REG(0x00u)
#define XND_RESULT           (*(volatile int32_t *)(XND_BASE+0x04u))
#define XND_OPERAND_A        XND_REG(0x08u)
#define XND_OPERAND_B        XND_REG(0x0cu)
#define XND_START            XND_REG(0x10u)
#define XND_A_ADDR           XND_REG(0x20u)
#define XND_W_ADDR           XND_REG(0x24u)
#define XND_Y_ADDR           XND_REG(0x28u)
#define XND_COLS             XND_REG(0x2cu)
#define XND_ROWS             XND_REG(0x30u)
#define XND_W_STRIDE_BYTES    XND_REG(0x34u)
#define XND_CTRL             XND_REG(0x38u)
#define XND_ERROR_CODE       XND_REG(0x3cu)
#define XND_CYCLES           XND_REG(0x40u)
#define XND_DMA_READ_BYTES    XND_REG(0x44u)
#define XND_DMA_WRITE_BYTES   XND_REG(0x48u)
#define XND_MACS             XND_REG(0x4cu)
#define XND_SLOT0_COLS       XND_REG(0x50u)
#define XND_SLOT1_COLS       XND_REG(0x54u)
/* Optional postprocess extension: bit0 enable, bits2:1 mode (0 quant,
 * 1 ReLU, 2 sat8+residual average), bits7:3 right shift. Reset defaults off.
 * Plain raw GEMV writes post_cfg=0 and keeps the original INT32 interface. */
#define XND_BIAS_ADDR        XND_REG(0x58u)
#define XND_POST_CFG         XND_REG(0x5cu)
#define XND_BUSY_MASK        0x1u
#define XND_DONE_MASK        0x2u
#define XND_ERROR_MASK       0x4u
#define XND_SLOT_VALID(slot) (0x100u << ((slot)&1u))
#define XND_CTRL_INT4        0x1u
#define XND_CTRL_IRQ         0x2u
#define XND_CMD_DOT4         1u
#define XND_CMD_LOAD         2u
#define XND_CMD_GEMV         3u
#define XND_CMD_INVALIDATE   4u
#define XND_COMMAND(op,slot) ((op)|(((slot)&1u)<<8))

enum xnd_error {
    XND_OK=0, XND_BAD_COMMAND=1, XND_BAD_PARAM=2, XND_OUT_OF_RAM=3,
    XND_SLOT_MISSING=4, XND_DMA_FAULT=5, XND_DMA_TIMEOUT=6
};

/* A software descriptor: no extra interpreter or compiler is required. */
typedef struct {
    uint32_t activation_addr;
    uint32_t weight_addr;
    uint32_t output_addr;
    uint32_t columns;
    uint32_t rows;
    uint32_t weight_stride_bytes; /* padded to a multiple of four bytes */
    uint32_t control;             /* INT4 / interrupt enable */
    uint32_t slot;                /* 0 or 1; explicit, predictable residence */
} xnd_job_t;

static inline void xnd_fence(void) {
#if defined(__riscv)
    __asm__ volatile ("fence iorw, iorw" ::: "memory");
#else
    __asm__ volatile ("" ::: "memory");
#endif
}

/* W1C means "write one to clear": reading STATUS never clears completion. */
static inline void xnd_ack(void) {
    XND_STATUS=XND_DONE_MASK|XND_ERROR_MASK;
    xnd_fence();
}

/* Bounded polling: 0 success, positive hardware error, -1 software timeout. */
static inline int xnd_wait(uint32_t max_polls) {
    while(max_polls--) {
        uint32_t s=XND_STATUS;
        if(s&XND_DONE_MASK) {
            xnd_fence();
            return (s&XND_ERROR_MASK) ? (int)XND_ERROR_CODE : XND_OK;
        }
    }
    return -1;
}

/* LOAD makes the vector resident; changing source RAM afterwards has no effect. */
static inline int xnd_load_activation(const xnd_job_t *job) {
    if(XND_STATUS&XND_BUSY_MASK) return -2;
    XND_A_ADDR=job->activation_addr;
    XND_COLS=job->columns;
    XND_CTRL=job->control;
    xnd_fence();
    XND_START=XND_COMMAND(XND_CMD_LOAD,job->slot);
    return XND_OK;
}

/* Reuse a resident vector against another weight matrix without another LOAD. */
static inline int xnd_launch_gemv(const xnd_job_t *job) {
    if(XND_STATUS&XND_BUSY_MASK) return -2;
    XND_W_ADDR=job->weight_addr;
    XND_Y_ADDR=job->output_addr;
    XND_COLS=job->columns;
    XND_ROWS=job->rows;
    XND_W_STRIDE_BYTES=job->weight_stride_bytes;
    XND_CTRL=job->control;
    xnd_fence();
    XND_START=XND_COMMAND(XND_CMD_GEMV,job->slot);
    return XND_OK;
}

static inline int xnd_invalidate(uint32_t slot) {
    if(XND_STATUS&XND_BUSY_MASK) return -2;
    XND_START=XND_COMMAND(XND_CMD_INVALIDATE,slot);
    return XND_OK;
}

/* Kept for the initial dot4 demonstration and scalar-vs-XND comparison. */
static inline int32_t xnd_dot4_mmio(uint32_t a,uint32_t b) {
    XND_OPERAND_A=a;
    XND_OPERAND_B=b;
    xnd_fence();
    XND_START=XND_CMD_DOT4;
    while((XND_STATUS&XND_DONE_MASK)==0u) { }
    xnd_fence();
    return XND_RESULT;
}

#endif
