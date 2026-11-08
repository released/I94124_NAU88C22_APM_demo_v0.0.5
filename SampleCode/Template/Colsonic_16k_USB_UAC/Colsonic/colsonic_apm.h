#ifndef __COLSONIC_APM_H
#define __COLSONIC_APM_H


#define	__COLSONIC_AEC_NS_ 		(1) 
#define __COLSONIC_Model_		__COLSONIC_AEC_NS_   //Selected algorithm.
 

#define FRM_LEN  320 


typedef unsigned int       uint32_t;
typedef int				   int32_t;
typedef unsigned short int uint16_t;
typedef short int          int16_t;
typedef unsigned char		uint8_t;
typedef float				float32_t;

 

/****************   APM      *******************/
/*
Initialize resources.
 
u32 init_ret = Colsonic_apm_init ( );
Returns 0 on success.
Returns a nonzero value on failure.
*/
uint32_t Colsonic_apm_init (  void) ;

/*Process one audio frame. 
mic_sig: microphone input signal.
ls_sig: loudspeaker (far-end) reference signal.
proc_out: processed output signal.
No return value.
Example:
Colsonic_apm_proc(mic_signal,ls_signal,out_signal);
*/
void Colsonic_apm_proc(  int16_t mic_sig[], int16_t ls_sig[], int16_t proc_out[]);

/*
Release resources:
*/
void Colsonic_apm_release ( void);
 
uint32_t colsonic_setpara_proc(uint32_t* ptr) ;

uint32_t Colsonic_ns_set(float percent);

#endif
