#include "misc.h"
#include "../../audio_channel.h"
#include <stdio.h>
#include <string.h> 
#include "Platform.h"
#include "init.h"
#include "usb_audio_def.h"
#include "usb_audio_const.h"
#include "pdma_config.h"
#include "data_handler.h"
#include "pdma_handler.h"
#include "setting.h"
#include "init_def.h"
#include "Trim.h"
#include "codec.h"
#include "buf_def.h"
#include "colsonic_apm.h"
#include "pdma_init.h"

UAC_PLAYBACK_T g_sUacPlayback = 
{
	.u8AudioSpeakerState = 0, 
	.u8BitRes = PLAY_BIT_RES,
	.u8SubFrm = (PLAY_BIT_RES>>3),
	.u8Channel = PLAY_CHANNELS,
	.u32PlaySampleRate = PLAY_RATE,

	.u16UAC_Buff_ReadIndex = 0,
	.u16UAC_Buff_WriteIndex = 0,
	.u16AvalCnt = 0,

	.usbd_PlayMute      = 0x0,     /* Play MUTE control. 0 = normal. 1 = MUTE */
	.usbd_PlayVolume    = 0x0,   /* Play channel volume. */
	.usbd_PlayMaxVolume = 0x0,
	.usbd_PlayMinVolume = 0x9d00,
	.usbd_PlayResVolume = 0x100, 
	
	.usbd_PlayCurVolume = 0x0,
	.usbd_PlayVolumeIndex = 0x0,
};

UAC_RECODER_T g_sUacRecord = 
{
	.u8AudioMicState = 0,
	.u8BitRes = MIC_BIT_RES,
	.u8SubFrm = (MIC_BIT_RES>>3),
	.u8Channel = REC_CHANNELS,
	.u32RecRate = REC_RATE,
	
	.u16UAC_Buff_ReadIndex = 0,
	.u16UAC_Buff_WriteIndex = 0,
	.u16AvalCnt = 0,		

	.usbd_RecMute       = 0x0,     /* Record MUTE control. 0 = normal. 1 = MUTE */
	.usbd_RecVolume     = 0x0,   /* Record channel volume.  */
	.usbd_RecMaxVolume  = 0x0,
	.usbd_RecMinVolume  = 0x9d00,
	.usbd_RecResVolume  = 0x100,
};


DATA_MANAGER g_sDataManager = 
{
	.u8I2S_Tx_Buff_Index = 0,
	.u16FarI2STmpWIdx = 0,
	.u8FarI2STmp_Buf_Idx = 0,
	
	.u8I2S_Rx_Buff_Index = 0,
	.u16NearI2STmpWIdx = 0,
	.u8NearI2STmp_Buf_Idx = 0,
	
	.u8DMIC_Buff_Index = 0,
	.u16NearDmicTmpWIdx = 0,
	.u8NearDmicTmp_Buf_Idx = 0,
	
	.bNearReady = FALSE,
	.bFarReady = FALSE,
	.bAlgEnable = FALSE,
	.bDoAECReady = FALSE,
	
	.psUacPlayback = &g_sUacPlayback,
	.psUacRecord = &g_sUacRecord,

};

void SysClk_Init(void)
{
	SysClk_Initiate();
//	CLK_SetPCLKDivider(CLK_PCLKDIV_PCLK0DIV4);	
//	CLK_SetPCLKDivider(CLK_PCLKDIV_PCLK1DIV4);	
}

void Codec_Init(void)
{
	CODEC_I2C1_Init(); 
#ifdef NAU88C22
	NAU88C22_Init(I2C1);
#endif
#ifdef NAU88L21
	NAU88L21_MicIn_Init(I2C1);
#endif
}

void Audio_Ip_Init(void)
{
	PDMA_Init();
		
    CODEC_I2S_Init_8822(UAC_RATE,UAC_DATA_BIT,UAC_RATE*256);	
	PDMA_I2S0_TX_Init(I2S0_TX_PDMA_CH);
	
#if NEAR_END_DMIC
	PDMA_DMIC_Init(DMIC_PDMA_CH);
	DMIC_Init(DMIC_RATE);
#else
	PDMA_I2S0_RX_Init(I2S0_RX_PDMA_CH);
#endif
}

void Misc(void)
{
	g_sDataManager.pu16Near = g_sDataManager.pu16Far = g_sDataManager.u16DecodeTmp;
	
	NVIC_SetPriority(USBD_IRQn, 1);  
	NVIC_SetPriority(PDMA_IRQn, 1); 
	
    I2S_CLR_TX_FIFO(I2S0);
	I2S_CLR_RX_FIFO(I2S0);	

#if NEAR_END_DMIC
	I2S_ENABLE_TXDMA(I2S0);
	I2S_ENABLE_TX(I2S0);		
	DMIC_ENABLE_PDMA(DMIC);
#else
	I2S_ENABLE_TXDMA(I2S0);
	I2S_ENABLE_TX(I2S0);
	I2S_ENABLE_RXDMA(I2S0);
	I2S_ENABLE_RX(I2S0);
#endif	
	SYS_Unlock();
	UART0_Init();	

	// HIRC Trim init
	SYS_SET_TRIMHIRC_LOOPSEL(SYS_IRCTCTL_LOOPSEL_4);
	SYS_SET_TRIMHIRC_RETRYCNT(SYS_IRCTCTL_RETRYCNT_64);
	SYS_ENABLE_TRIMHIRC_CLKERRSTOP();
	SYS_SET_TRIMHIRC_REFCLK(SYS_IRCTCTL_REFCLK_USBSOF);

	USBD_Init();
	USBD_Start();
	
}

void hw_play_reset(void)
{

}

void hw_play_start(void)
{	

}

void hw_play_close(void)
{

}

void hw_rec_start(void)
{	
	g_sDataManager.u16NearI2STmpWIdx = 0;
	g_sDataManager.u8NearI2STmp_Buf_Idx = 0;
	g_sDataManager.bNearReady = FALSE;

	g_sDataManager.bFarReady = FALSE;
	g_sDataManager.u16FarI2STmpWIdx = 0;
	g_sDataManager.u8FarI2STmp_Buf_Idx = 0;	
		
	g_sDataManager.u16DecodeAvalCnt = 0;
	g_sDataManager.u16DecodeBufRIdx = 0;
	g_sDataManager.u8Decode_Buf_Idx = 0;
	g_sDataManager.bAlgEnable = TRUE;
	g_sDataManager.bDoAECReady = FALSE;
	
}

void hw_rec_close(void)
{
	g_sDataManager.bAlgEnable = FALSE;
	
}

void Colsonic_Init(void)
{
	Colsonic_apm_init();
    /* Keep the same NS preset after APM initialization or reset. */
	Colsonic_ns_set(0.85f);
}

void Colsonic_Work_Handle(void)
{
	uint16_t i;

	if(g_sDataManager.bDoAECReady)	
	{		
		Colsonic_apm_proc((int16_t *)g_sDataManager.pu16Near, 
						  (int16_t *)g_sDataManager.pu16Far,
						  (int16_t *)g_sDataManager.u16DecodeTmp);
		NVIC_DisableIRQ(PDMA_IRQn);
		g_sDataManager.bDoAECReady = FALSE;
		NVIC_EnableIRQ(PDMA_IRQn);
		
        /* GoldWave: left is raw microphone; right is processed voice. */
        for(i = 0; i < COLSONIC_DAT_LEN; i++)
        {
            g_sDataManager.u32Decode[g_sDataManager.u8Decode_Buf_Idx][i] =
                Audio_PackStereo(g_sDataManager.pu16Near[i],
                                 g_sDataManager.u16DecodeTmp[i]);
        }
		g_sDataManager.u16DecodeAvalCnt += COLSONIC_DAT_LEN;
		g_sDataManager.u8Decode_Buf_Idx ^= 1;
	}		
}
