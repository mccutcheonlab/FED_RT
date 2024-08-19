# REALTIME_REMOTE_FED(RTFED)
### What is RTFED?
**RTFED** is a software update to the open-source automated feeding/operant_reward machine [FED3](https://github.com/KravitzLabDevices/FED3/wiki). This update enables you to collect data from FED3 online and remotely without needing any additional hardware change.(e.g. directly to a Google spreadsheet instead of writing to the SD card). Moreover here I share a walkthrough of the process of incorporating a Google Apps Script with your spreadsheet to send you an alarm email in case your FED3 fails to deliver a pellet (e.g. jamming happens)

*Since you need to have your FED3 connected to a computer via a USB cable all the time, this solution works best for labs who do not place the FED3 inside the mouse cage or can protect the FED3 and cable from the mice.*

*So far it has been tested on Windows and Mac and it works fine on both operating systems.*

### Step by step instructions for setting up RTFED
#### 1) Update FED3 library with NEW FILES and flash the board
The process of  flashing FED3 is explained in detail on the original [FED3 repository](https://github.com/KravitzLabDevices/FED3_library), the only process you need to follow is to go to your Arduino library folder, find the FED3 library and in folder **/scr** replace the FED3.h and FED3.cpp files with files provided here [FED3_Library](https://github.com/Htbibalan/FED_RT/tree/main/source/FED3_Library). 
After replacing the files,  connect your FED3 to your computer, put it on boot loader mode and flash it just as explained in the original FED3 repository. 

Optional: You can also flash your board with a new "ClassicFED3.ino" file available [here](https://github.com/Htbibalan/FED_RT/tree/main/source/FED3_Library/ClassicFED3), this file includes Closed_economy mode in addition to previous modes included in original ClassicFED3.

**note: There are several changes in this new update of library(this topic is under_construction)**

## Step 0: Create a Google spreadsheet in your Google Drive, we will get back to it later

## Step 1: Create a project
To automatically send data from a local script to a specific Google Spreadsheet we need to get Google Service Account credentials which enables your python script to authenticate as a specific account without needing user interaction each time.


1) Go to this [link](https://console.cloud.google.com/projectcreate) to create a new project on you Google Cloud Console, as shown on  the screenshot, assign a name to it and press create.
![create_project](https://github.com/Htbibalan/FED_RT/blob/main/source/Images/project_create_1.png)

As soon as you create the project you will be prompted to a new link where you will see notifications on the right corner bell, and the image below should show up, if not, click on the notification icon and click on the last notification which says "project is created".

![notification](https://github.com/Htbibalan/FED_RT/blob/main/source/Images/notification_3.png)

## Step 2: Set up Service Account Credentials (Get JSON file)
Once in the control panel of your project, form the left side panel go to API and Services and then select Library.

![Control_panel](https://github.com/Htbibalan/FED_RT/blob/main/source/Images/project_create_2.png)

A new link will open in the search bar look for Google Drive API.
Select the Google Drive API (probably the first item) and then ENABLE it. It will open a new link where you can control parameters of your Google Drive API

![API_SEARCH](https://github.com/Htbibalan/FED_RT/blob/main/source/Images/API_LIB_Search_5.png)
![API_ENABLE](https://github.com/Htbibalan/FED_RT/blob/main/source/Images/select_google_drive_API_ENABLE_6.png)



In GOOGLE DRIVE API control panel, go to Credentials in the left panel menu and then select **+ CREATE CREDENTIALS** and from the menu select **Service Account**
![API_CONTROL_PANEL](https://github.com/Htbibalan/FED_RT/blob/main/source/Images/API_CONTROL_PANEL.png)
![API_SERVICE_ACOUNT](https://github.com/Htbibalan/FED_RT/blob/main/source/Images/API_CREDENTIAL_SERVICE_ACOUNT.png)


Enter a service account name and Service ID will be filled automatically,  then press Create and Continue, you can optionally add more users to your project or just press DONE (You can manage it later if needed)
![API_SERVICE_ACOUNT](https://github.com/Htbibalan/FED_RT/blob/main/source/Images/API_SERVICE_NAME_TEST.png)


Now on the dashboard of your APIs and Services of your project, in Credentials tab from the left panel, you will find Service Account created. Under **Action** click on the edit icon (pen icon)
![API_SERVICE_ACOUNT](https://github.com/Htbibalan/FED_RT/blob/main/source/Images/API_KEY_CREATE.png)

Click on KEYS
![PRESS_KEY](https://github.com/Htbibalan/FED_RT/blob/main/source/Images/Press_KEY.png)

Now click on ADD KEY and then create a JSON file.

![JSON](https://github.com/Htbibalan/FED_RT/blob/main/source/Images/API_KEY_JSON.png)

As soon as you create the JSON key a file is downloaded, take that file and copy it to your preferred location, we will use this file location in the python script. This JSON file contains information that enables you to interact with the python script and spreadsheet.

## Step 3: Enable the Google Sheets API:

Still within the APIs & Services > Credentials page, go to the Library section and search for Google Sheets API.

![API_SEARCH](https://github.com/Htbibalan/FED_RT/blob/main/source/Images/API_LIB_Search_5.png)

Select Google Sheets API and then click Enable to activate it for your project.

![GOOGLESHEETS_API](https://github.com/Htbibalan/FED_RT/blob/main/source/Images/Activate_GOOGLE_SHEETS_API.png)

## Step 4: Key step - get email add from JSON file
Now to allow the Service Account access the Google spreadsheet we need to share the Google spreadsheet with the email associated with your Service account (Go to the JSON file)

1) Open  the JSON file that you just downloaded, it can be opened in any editor(like notepad or VSCode).
2) In  the JSON file you will find the "client email", copy that email address(the quotation mark is not needed)
3) Go to your Google spreadsheet on your Google drive , click on Share icon on the far right of the screen, Paste the email address from the JSON file and click done, you can edit different levels of access for other people as well.


## Step 5: Open your python IDE(e.g. Jupyter lab) and copy the code from this repository
 With everything setup to this stage, go to the python script provided here [RTFED](https://github.com/Htbibalan/FED_RT/blob/main/scripts/RTFED.ipynb) and replace the variables according to your own spreadsheet and file path.

Replace the CREDS_FILE directory with the pathway to you JSON file.

Find you Google spreadsheet ID, open the spreadsheet and in the address bar, copy everything between d/.../edit as shown in the image below
 ![SHEET_ID](https://github.com/Htbibalan/FED_RT/blob/main/source/Images/SHEET_ID.png)



























