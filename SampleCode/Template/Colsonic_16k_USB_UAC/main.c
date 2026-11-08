#include "misc.h"
#include "colsonic_para_set.h"

//----------------------------------------------------------------------------
//  MAIN function
//----------------------------------------------------------------------------
int main(void)
{	
	SysClk_Init();
	
	Colsonic_Init();
	
	Codec_Init();
	
	Audio_Ip_Init();
	
	Misc();

	
	while(1)
	{
		Colsonic_Work_Handle();
		Main_Console_Handle();
	}
}

