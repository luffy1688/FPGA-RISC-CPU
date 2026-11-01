/* 必要验收：同图6->2LOAD、last-use释放、第三活跃输入/超容量拒绝。 */
#include "../../03_sw/model/tensor_plan.h"
#include "../../03_sw/model/byte_tool_model.h"
#include <stdio.h>
static int8_t a[64],b[64],c[64];
static int run(unsigned mode) {
    nr_tensor_residence_t state;
    const int8_t *input[]={a,b,a,b,a,b};
    unsigned flags[]={0,0,NR_GEMV_REUSE_INPUT,NR_GEMV_REUSE_INPUT,
        NR_GEMV_REUSE_INPUT|NR_GEMV_LAST_USE,NR_GEMV_REUSE_INPUT|NR_GEMV_LAST_USE};
    unsigned index,slot,loads=0;
    int reuse;
    nr_tensor_reset(&state);
    for(index=0;index<6;index++) {
        if(nr_tensor_choose(&state,mode,input[index],64,flags[index],3,&slot,&reuse)) return -1;
        if(!reuse) {loads++;nr_tensor_commit(&state,slot,input[index],64);}
        if(flags[index]&NR_GEMV_LAST_USE) nr_tensor_release(&state,slot);
    }
    if(state.valid[0] || (mode==3 && state.valid[1])) return -1;
    return (int)loads;
}
int main(void) {
    nr_tensor_residence_t state;
    unsigned slot;
    int reuse;
    if(run(1)!=6 || run(2)!=6 || run(3)!=2) return 1;
    nr_tensor_reset(&state);
    nr_tensor_commit(&state,0,a,64);nr_tensor_commit(&state,1,b,64);
    if(nr_tensor_choose(&state,3,c,64,0,3,&slot,&reuse)!=NR_TENSOR_NO_SLOT) return 2;
    if(nr_tensor_choose(&state,3,c,257,0,3,&slot,&reuse)!=-1) return 3;
    nr_tensor_release(&state,0);
    if(nr_tensor_choose(&state,3,c,64,0,3,&slot,&reuse) || slot!=0 || reuse) return 4;
    nr_tensor_commit(&state,0,c,64);
    if(nr_tensor_choose(&state,3,c,64,0,3,&slot,&reuse) || reuse) return 5;
    puts("PASS TENSOR_PLAN: reload=6 single=6 lifetime=2; 2x256B capacity, last-use and mutable-content rules");
    return 0;
}
