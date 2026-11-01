/* NeedleRV-X CoreMark port: standard volatile seeds and real CPU cycle timer.
 * Only platform functions are changed; benchmark algorithms are unmodified. */
#include "coremark.h"
#include "fixed_ratio.h"
#include "../platform/needle_pmu.h"
#if VALIDATION_RUN
volatile ee_s32 seed1_volatile=0x3415, seed2_volatile=0x3415;
#else
volatile ee_s32 seed1_volatile=0, seed2_volatile=0;
#endif
volatile ee_s32 seed3_volatile=0x66, seed4_volatile=ITERATIONS, seed5_volatile=0;
ee_u32 default_num_contexts=1;
static ee_u32 t0,t1;
static nr_pmu_t pmu_begin,pmu_end;
static ee_u32 cycle_lo(void) { ee_u32 v; __asm__ volatile("csrr %0,cycle":"=r"(v)); return v; }
void start_time(void) { nr_pmu_snapshot(&pmu_begin); t0=cycle_lo(); }
void stop_time(void) { t1=cycle_lo(); nr_pmu_snapshot(&pmu_end); *(volatile ee_u32*)0x10000130u=1; }
CORE_TICKS get_time(void) { return (ee_u32)(t1-t0); }
secs_ret time_in_secs(CORE_TICKS ticks) { return ticks/CPU_HZ; }
void portable_init(core_portable *p,int *argc,char *argv[]) {
  (void)argc; (void)argv;
  if(sizeof(ee_ptr_int)!=sizeof(void*) || sizeof(ee_u32)!=4) ee_printf("ERROR! port types\n");
  p->portable_id=1;
}
void portable_fini(core_portable *p) {
  p->portable_id=0;
  // Timed region is over: print raw cycles and retire/cache/branch evidence.
  ee_u32 ir,br,mp,st,ic,dc;
  __asm__ volatile("csrr %0,instret":"=r"(ir));
  __asm__ volatile("csrr %0,0xb03":"=r"(br));
  __asm__ volatile("csrr %0,0xb04":"=r"(mp));
  __asm__ volatile("csrr %0,0xb05":"=r"(st));
  __asm__ volatile("csrr %0,0xb06":"=r"(ic));
  __asm__ volatile("csrr %0,0xb07":"=r"(dc));
  ee_printf("NR_CYCLES=%u NR_HZ=%u NR_ITERATIONS=%u\n",get_time(),CPU_HZ,(ee_u32)seed4_volatile);
  /* Precise fixed-point supplemental timer, outside the measured algorithm.
   * EEMBC's HAS_FLOAT=0 legacy line truncates seconds; do not use its
   * integer Iterations/Sec value as the cycle-normalized reported score. */
  {
    ee_u32 ticks=get_time();
    ee_u32 frac=nr_report_div_u64_u32((uint64_t)(ticks%CPU_HZ)*1000000u,CPU_HZ);
    ee_u32 score=nr_report_div_u64_u32((uint64_t)(ee_u32)seed4_volatile*1000000000000ull,ticks);
    ee_printf("NR_COREMARK_PRECISE seconds=%u.%06u coremark_per_mhz=%u.%06u legacy_seconds_truncated=1\n",
              ticks/CPU_HZ,frac,score/1000000u,score%1000000u);
  }
  ee_printf("BOOT_INSTRET=%u BRANCHES=%u MISPREDICTS=%u STALLS=%u IC_MISSES=%u DC_MISSES=%u\n",ir,br,mp,st,ic,dc);
  nr_pmu_t d=nr_pmu_delta(&pmu_begin,&pmu_end);
  ee_printf("NR_PMU {\"scope\":\"coremark_bracket\",\"cycles\":%u,\"instret\":%u,"
            "\"branches\":%u,\"redirect_misses\":%u,\"mem_load_stall_cycles\":%u,"
            "\"ic_misses\":%u,\"dc_misses\":%u}\n",
            d.cycles,d.instret,d.branches,d.redirect_misses,d.mem_load_stall_cycles,d.ic_misses,d.dc_misses);
  // GPIO completion marker is observable by real board and simulation alike.
#if defined(NR_COREMARK_LIBRARY)
  ee_printf("NR_COREMARK_RETURN\n");
#else
  *(volatile ee_u32*)0x10000004u=0xc0;
#endif
}
