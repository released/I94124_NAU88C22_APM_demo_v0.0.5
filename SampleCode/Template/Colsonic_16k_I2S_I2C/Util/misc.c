#include "misc.h"
#include "../../audio_channel.h"
#include <stdio.h>
#include <string.h> 
#include "Platform.h"
#include "init.h"
#include "usb_audio_def.h"
#include "usb_audio_const.h"
#include "data_handler.h"
#include "pdma_handler.h"
#include "setting.h"
#include "init_def.h"
#include "Trim.h"
#include "codec.h"
#include "colsonic_apm.h"
#include "pdma_init.h"


extern void Start_Audio(void);

DATA_MANAGER g_sDataManager = 
{
	.u8I2S_Tx_Buff_Index = 0,
	.u16FarI2STmpWIdx = 0,
	.u8FarI2STmp_Buf_Idx = 0,
	
	.u8I2S_Rx_Buff_Index = 0,
	.u16NearI2STmpWIdx = 0,
	.u8NearI2STmp_Buf_Idx = 0,
	
//	.u8DMIC_Buff_Index = 0,
//	.u16NearDmicTmpWIdx = 0,
//	.u8NearDmicTmp_Buf_Idx = 0,
	
	.bI2S_Tx_Mute = 0,
	
	.u8Decode_Buf_Idx = 0,
	.u16DecodeBufRIdx = 0,
	.u16DecodeAvalCnt = 0,
	
	.bNearReady = FALSE,
	.bFarReady = FALSE,
	.bByPass = FALSE,
	
};
	

void SysClk_Init(void)
{
	SysClk_Initiate();
	CLK_SetPCLKDivider(CLK_PCLKDIV_PCLK0DIV4);	
	CLK_SetPCLKDivider(CLK_PCLKDIV_PCLK1DIV4);	
}

void Codec_Init(void)
{
	CODEC_I2C1_Init(); 
	
	NAU88C22_Init(I2C1);
}

void Audio_Ip_Init(void)
{
	PDMA_Init();
		
    CODEC_I2S_Init_8822(UAC_RATE,UAC_DATA_BIT,UAC_RATE*256);	
	PDMA_I2S0_TX_Init(I2S0_TX_PDMA_CH);
	PDMA_I2S0_RX_Init(I2S0_RX_PDMA_CH);
	
	#if !defined (USB_EVB_SPI2_I2S)
	SPI1_I2S_Init(UAC_RATE);
	PDMA_SPI1_I2S_TX_Init(SPI1_I2S_TX_PDMA_CH);
	PDMA_SPI1_I2S_RX_Init(SPI1_I2S_RX_PDMA_CH);
	#else
	SPI2_I2S_Init(UAC_RATE);
	PDMA_SPI2_I2S_TX_Init(SPI2_I2S_TX_PDMA_CH);
	PDMA_SPI2_I2S_RX_Init(SPI2_I2S_RX_PDMA_CH);	
	#endif

	TMR3_Init();
}

void Misc(void)
{
	g_sDataManager.pu16Near = g_sDataManager.pu16Far = g_sDataManager.u16DecodeTmp;
	g_sDataManager.bByPass = FALSE;
	
	NVIC_SetPriority(USBD_IRQn, 1);  
	NVIC_SetPriority(PDMA_IRQn, 1); 

//	GPIO_SetMode(PB,BIT0,GPIO_MODE_OUTPUT); // for D4 on EVB
//	PB0 = 1; // D4 Off

	// gpio not used set qusi-high
//	{
//		PA->MODE |= 0xffc03fff;
//		PB->MODE |= 0xe003ffff;
//		PC->MODE |= 0xffffff00;
//		PD->MODE |= 0x0cc0c000;
//	}
	
	UART0_Init();	
	
	I2C0_Slave_Init();
	
#if 1	// need to trigger ?
  	Start_Audio();
#endif

	printf("\r\n%s\r\n",__FUNCTION__);
	printf("AEC/NR BY PASS:%s\r\n", (g_sDataManager.bByPass == TRUE) ? ("ENABLE") : ("DISABLE") );

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

}

void hw_rec_close(void)
{
	
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

	if(g_sDataManager.bNearReady)	
	{	
		Colsonic_apm_proc((int16_t *)g_sDataManager.pu16Near, 
							  (int16_t *)g_sDataManager.pu16Far,
							  (int16_t *)g_sDataManager.u16DecodeTmp);

		NVIC_DisableIRQ(PDMA_IRQn);
		g_sDataManager.bNearReady = FALSE;
		NVIC_EnableIRQ(PDMA_IRQn);
		
		if(g_sDataManager.bByPass == FALSE)
		{
			for(i = 0;i < COLSONIC_DAT_LEN; i++)
			{
				g_sDataManager.u32Decode[g_sDataManager.u8Decode_Buf_Idx][i] = 
                    Audio_PackStereo(g_sDataManager.pu16Near[i],
                                     g_sDataManager.u16DecodeTmp[i]);
			}
		}
		else
		{
			for(i = 0;i < COLSONIC_DAT_LEN; i++)
			{
                /* Keep the voice uplink on the right in bypass mode. */
				g_sDataManager.u32Decode[g_sDataManager.u8Decode_Buf_Idx][i] = 
                    Audio_PackStereo(g_sDataManager.pu16Far[i],
                                     g_sDataManager.pu16Near[i]);
			}			
		}
		
		g_sDataManager.u16DecodeAvalCnt += COLSONIC_DAT_LEN;
		g_sDataManager.u8Decode_Buf_Idx ^= 1;
	}	

	
}

void Start_Audio(void)
{	
	CODEC_I2S_Init_8822(UAC_RATE,UAC_DATA_BIT,UAC_RATE*256);
	
	PDMA_I2S0_TX_Init(I2S0_TX_PDMA_CH);
	PDMA_I2S0_RX_Init(I2S0_RX_PDMA_CH);	

	#if !defined (USB_EVB_SPI2_I2S)
	SPI1_I2S_Init(UAC_RATE);
	PDMA_SPI1_I2S_TX_Init(SPI1_I2S_TX_PDMA_CH);
	PDMA_SPI1_I2S_RX_Init(SPI1_I2S_RX_PDMA_CH);
	#else
	SPI2_I2S_Init(UAC_RATE);	
	PDMA_SPI2_I2S_TX_Init(SPI2_I2S_TX_PDMA_CH);
	PDMA_SPI2_I2S_RX_Init(SPI2_I2S_RX_PDMA_CH);	
	#endif
	
	g_sDataManager.pu16Near = g_sDataManager.pu16Far = g_sDataManager.u16DecodeTmp;
		
    I2S_CLR_TX_FIFO(I2S0);
	I2S_CLR_RX_FIFO(I2S0);	

	I2S_ENABLE_TXDMA(I2S0);
	I2S_ENABLE_TX(I2S0);
	I2S_ENABLE_RXDMA(I2S0);
	I2S_ENABLE_RX(I2S0); 

	#if !defined (USB_EVB_SPI2_I2S)
	SPI_I2S_ENABLE_TX(SPI1);	
	SPI_I2S_ENABLE_RX(SPI1);
	SPI_I2S_ENABLE_TXDMA(SPI1);
	SPI_I2S_ENABLE_RXDMA(SPI1);
	SPI_I2SEnableControl(SPI1);	
	#else
	SPI_I2S_ENABLE_TX(SPI2);	
	SPI_I2S_ENABLE_RX(SPI2);
	SPI_I2S_ENABLE_TXDMA(SPI2);
	SPI_I2S_ENABLE_RXDMA(SPI2);	
	SPI_I2SEnableControl(SPI2);	
	#endif
	
 	g_sDataManager.u16NearI2STmpWIdx = 0;
	g_sDataManager.u8NearI2STmp_Buf_Idx = 0;
	g_sDataManager.bNearReady = FALSE;

	g_sDataManager.bFarReady = FALSE;
	g_sDataManager.u16FarI2STmpWIdx = 0;
	g_sDataManager.u8FarI2STmp_Buf_Idx = 0;	
	
	g_sDataManager.u16DecodeAvalCnt = 0;
	g_sDataManager.u16DecodeBufRIdx = 0;
	g_sDataManager.u8Decode_Buf_Idx = 0;
	
//	PB0 = 0;
	printf("\r\n%s\r\n",__FUNCTION__);
}

void Stop_Audio(void)
{
	I2S_DISABLE_RX(I2S0);
	I2S_DISABLE_TX(I2S0);
	I2S_DISABLE_RXDMA(I2S0);
	I2S_DISABLE_TXDMA(I2S0);		
	I2S_DISABLE(I2S0);	

	#if !defined (USB_EVB_SPI2_I2S)
	SPI_I2S_DISABLE_TX(SPI1);	
	SPI_I2S_DISABLE_RX(SPI1);
	SPI_I2S_DISABLE_TXDMA(SPI1);
	SPI_I2S_DISABLE_RXDMA(SPI1);
	SPI_I2SDisableControl(SPI1);
	#else
	SPI_I2S_DISABLE_TX(SPI2);	
	SPI_I2S_DISABLE_RX(SPI2);
	SPI_I2S_DISABLE_TXDMA(SPI2);
	SPI_I2S_DISABLE_RXDMA(SPI2);
	SPI_I2SDisableControl(SPI2);
	#endif
	
	PDMA_Close();

	g_sDataManager.u8I2S_Tx_Buff_Index = 0;
	g_sDataManager.u16FarI2STmpWIdx = 0;
	g_sDataManager.u8FarI2STmp_Buf_Idx = 0;
	
	g_sDataManager.u8I2S_Rx_Buff_Index = 0;
	g_sDataManager.u16NearI2STmpWIdx = 0;
	g_sDataManager.u8NearI2STmp_Buf_Idx = 0;

	g_sDataManager.u16SPI_I2S_Tx_Buff_ReadIndex = 0;
	g_sDataManager.u16SPI_I2S_Tx_Buff_WriteIndex = 0;
	g_sDataManager.u16SPI_I2S_Tx_AvalCnt = 0;

	g_sDataManager.u16SPI_I2S_Rx_Buff_ReadIndex = 0;
	g_sDataManager.u16SPI_I2S_Rx_Buff_WriteIndex = 0;
	g_sDataManager.u16SPI_I2S_Rx_AvalCnt = 0;
	
 	g_sDataManager.u16NearI2STmpWIdx = 0;
	g_sDataManager.u8NearI2STmp_Buf_Idx = 0;
	g_sDataManager.bNearReady = FALSE;

	g_sDataManager.bFarReady = FALSE;
	g_sDataManager.u16FarI2STmpWIdx = 0;
	g_sDataManager.u8FarI2STmp_Buf_Idx = 0;	
	
	g_sDataManager.u16DecodeAvalCnt = 0;
	g_sDataManager.u16DecodeBufRIdx = 0;
	g_sDataManager.u8Decode_Buf_Idx = 0;

	Colsonic_apm_init();
		
//	PB0 = 1;
    /* Keep the same NS preset after APM initialization or reset. */
	Colsonic_ns_set(0.85f);
	printf("\r\n%s\r\n",__FUNCTION__);
}

void Set_AEC_ByPass(uint8_t u8OnOff)
{
	if(u8OnOff)
	{
		g_sDataManager.bByPass = TRUE;
		// PB0 = 0;
		printf("\r\n%s:%s\r\n",__FUNCTION__, (u8OnOff == TRUE) ? ("ENABLE") : ("DISABLE") );
	}
	else
	{
		g_sDataManager.bByPass = FALSE;
		// PB0 = 1;
		printf("\r\n%s:%s\r\n",__FUNCTION__, (u8OnOff == TRUE) ? ("ENABLE") : ("DISABLE") );
	}
}


void Set_I2S_Tx_Mute(uint8_t u8OnOff)
{
	if(u8OnOff)
	{
		g_sDataManager.bI2S_Tx_Mute = TRUE;
		// printf("\r\n%s:%d\r\n",__FUNCTION__,u8OnOff);
	}
	else
	{
		g_sDataManager.bI2S_Tx_Mute = FALSE;
		// printf("\r\n%s:%d\r\n",__FUNCTION__,u8OnOff);
	}
}

