//colsonic_def.h
#ifndef COLSONICDEF_H_
#define COLSONICDEF_H_
#include <stdio.h>
#include <stdlib.h>

extern unsigned long int u32CMDDataBegin;
extern unsigned long int u32CMDDataEnd;


#define COLSONIC_BUF_LEN_MODE  (85*1024)
#define COLSONIC_AEC_LEN   (800)

extern volatile __attribute__((aligned(4))) unsigned char APM_MemPool[COLSONIC_BUF_LEN_MODE];
extern   unsigned int   colsonic_lib_buf_len;
extern   unsigned int   colsonic_lib_aec_len ;


#endif /* COLSONICDEF_H_ */
