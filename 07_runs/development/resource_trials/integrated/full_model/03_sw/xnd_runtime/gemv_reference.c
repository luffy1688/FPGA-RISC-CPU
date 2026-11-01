#include <stdint.h>
/*
 * Golden software kernel. It defines the exact packing and arithmetic used
 * by hardware. Accumulation is INT32; there is no hidden requantization.
 * INT4 is two's complement [-8,7], low nibble = smaller column.
 */
static int32_t signed_nibble(uint8_t nibble) {
    nibble&=15u;
    return (nibble&8u) ? (int32_t)nibble-16 : (int32_t)nibble;
}
void xnd_gemv_reference(const int8_t *activation,const uint8_t *weights,
                        int32_t *output,uint32_t rows,uint32_t columns,
                        uint32_t stride_bytes,int use_int4) {
    for(uint32_t r=0;r<rows;r++) {
        int32_t sum=0;
        const uint8_t *row=weights+r*stride_bytes;
        for(uint32_t c=0;c<columns;c++) {
            int32_t w=use_int4 ?
              signed_nibble((uint8_t)(row[c>>1]>>((c&1u)*4u))) :
              (int32_t)(int8_t)row[c];
            sum+=(int32_t)activation[c]*w;
        }
        output[r]=sum;
    }
}

/* Saturating symmetric quantization is done by the exporter, not the GEMV. */
void xnd_pack_int4_row(const int8_t *weights,uint8_t *packed,
                      uint32_t columns,uint32_t padded_bytes) {
    for(uint32_t i=0;i<padded_bytes;i++) packed[i]=0;
    for(uint32_t c=0;c<columns;c++) {
        int32_t w=weights[c];
        if(w<-8) w=-8;
        if(w>7) w=7;
        packed[c>>1]|=(uint8_t)(((uint32_t)w&15u)<<((c&1u)*4u));
    }
}
