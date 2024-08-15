# FED_Realtime_Remote(FED_RT)
### What is FED_RT?
FED_RT is a software update to the open-source automated feeding/operant_reward machine [FED3](https://github.com/KravitzLabDevices/FED3/wiki). This update enables you to collect data from FED3 online and remotely without needing any additional hardware change.(e.g. directly to a google spreadsheet instead of writing to the SD card). Moreover here I share a walkthrough of the process of incorporating a Google Apps Script with you spreadsheet to send you an alarm email in case your FED3 fails to deliver a pellet (i.e jamming happens)

*Since you need to have your FED3 connected to a computer via a USB cable all the time, this solution works best for labs who do not place the FED3 inside the mouse cage or can protect the FED3 and cable from the mice*

*So far it has been tested on Windows and Mac and it works fine on both operating systems*

### Step by step instructions for setting up FED_RT
#### 1) Update FED3 library and flash the board
The process of  flashing FED3 is explained in detail on the original [FED3 repository](https://github.com/KravitzLabDevices/FED3_library), the only process you need to follow is to go to your Arduino library folder, find the FED3 library and in folder */scr* replace the FED3.h and FED3.cpp files with files provided here [FED3_Library](https://github.com/Htbibalan/FED_RT/tree/main/source/FED3_Library). 
After replacing the files,  connect your FED3 to your computer, put it on boot loader mode and flash it just as explained in the original FED3 repository. 

#### 



