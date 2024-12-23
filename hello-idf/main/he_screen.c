#include "he_screen.h"


static void Draw(void *pvParameters)
{
    WATCHDOG_ADD

	uint16_t CurrentColor = BLUE;
	while (1){
		if(xpt2046_read()){
            ESP_LOGI(TAG,"Touch: %d, %d", TouchX, TouchY);

			if(TouchY<=30 && TouchX<=30){
                mostra_info_sd(SD_MOUNT_POINT);       

				CurrentColor = BLUE;
			}else if(TouchY<=30 && TouchX>30 && TouchX<60){
				CurrentColor = BROWN;
			}else if(TouchY<=30 && TouchX>60 && TouchX<90){
				CurrentColor = GREEN;
			}else if(TouchY<=30 && TouchX>90 && TouchX<120){
				CurrentColor = GBLUE;
			}else if(TouchY<=30 && TouchX>120 && TouchX<150){
				CurrentColor = RED;
			}else if(TouchY<=30 && TouchX>150 && TouchX<180){
				CurrentColor = MAGENTA;
			}else if(TouchY<=30 && TouchX>180 && TouchX<210){
				CurrentColor = YELLOW;
			}else if(TouchY<=30 && TouchX>210 && TouchX < 240){
				LCD_DrawFillRectangle(0,31,240,320,WHITE);
			}
			else{
				LCD_DrawPoint1(TouchX,TouchY,CurrentColor);//画点 
			}
		}

        WATCHDOG_RESET
		vTaskDelay(10 / portTICK_PERIOD_MS);
	}

    WATCHDOG_END
	vTaskDelete(NULL);
}

void init_tft(void)
{
	esp_err_t ret;
	ESP_LOGI(TAG, "Init LCD...");
	Init_LCD(WHITE);
	//初始化 XPT2046
	xpt2046_init();
	LCD_Set_Orientation(LCD_DISPLAY_ORIENTATION_LANDSCAPE_INVERTED);// 纵向翻转
	
    //TP_Adjust(); // Serve per calibrare lo schermo
    
	// 实心矩形
	LCD_DrawFillRectangle(0,0,30,30,BLUE);
	LCD_DrawFillRectangle(30,0,60,30,BROWN);
	LCD_DrawFillRectangle(60,0,90,30,GREEN);
	LCD_DrawFillRectangle(90,0,120,30,GBLUE);
	LCD_DrawFillRectangle(120,0,150,30,RED);
	LCD_DrawFillRectangle(150,0,180,30,MAGENTA);
	LCD_DrawFillRectangle(180,0,210,30,YELLOW);
	LCD_DrawRectangle(210,0,240,30,RED);
	LCD_ShowString(215,9,WHITE,BLACK,16,"Cle",0);
	LCD_DrawFillRectangle(0,31,240,320,WHITE);
	xTaskCreate(&Draw, "Draw", 4096, NULL, 5, NULL);
}
