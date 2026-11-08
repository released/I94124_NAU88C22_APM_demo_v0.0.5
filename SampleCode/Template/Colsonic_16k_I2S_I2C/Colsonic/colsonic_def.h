//colsonic_def.h
#ifndef COLSONICDEF_H_
#define COLSONICDEF_H_
#include <stdio.h>
#include <stdlib.h>

#define COLSONIC_BUF_LEN_MODE  (85*1024)
extern volatile __attribute__((aligned(4))) unsigned char APM_MemPool[COLSONIC_BUF_LEN_MODE];
extern   unsigned int   colsonic_lib_buf_len;

#endif /* COLSONICDEF_H_ */
