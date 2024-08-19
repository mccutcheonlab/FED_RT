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

## Step 1: Set up Google Sheets API
To automatically send data from a local script to a specific Google Spreadsheet we need to get Google Service Account credentials which enables your python script to authenticate as a specific account without needing user interaction each time.


1) Go to this [link](https://console.cloud.google.com/projectcreate) to create a new project on you Google Cloud Console, as shown on  the screenshot, assign a name to it and press create.
![create_project](https://github.com/Htbibalan/FED_RT/blob/main/source/Images/project_create_1.png)

As soon as you create the project you will be prompted to a new link where you will see notifications on the right corner bell, and the image below should show up, if not, click on the notification icon and click on the last notification which says "project is created".
![notification](https://github.com/Htbibalan/FED_RT/blob/main/source/Images/notification_3.png)
Once in the control panel, form the left side panel go to API and Services and then select Library 
![Control_panel](https://github.com/Htbibalan/FED_RT/blob/main/source/Images/project_create_2.png)

a new link will open

in the search bar look for Google Drive API
![API_SEARCH](https://github.com/Htbibalan/FED_RT/blob/main/source/Images/API_LIB_Search_5.png)
![API_ENABLE](https://github.com/Htbibalan/FED_RT/blob/main/source/Images/select_google_drive_API_ENABLE_6.png)

Select the Google Drive API (probably the first item) and then ENABLE it. it will open a new link where you can control parameters of your Google Drive API

in GOOGLE DRIVE API control panel, go to Credentials in the left panel menu
select +CREATE CREDENTIALS and from the Menu select OAuth cleint ID

In the new link, select CONFIGURE CONSENT SCREEN

Select External and press Create
Fill th required information , use your own gmail address whenever asked, and click SAVE and CONTINUE and keep pressing it in the next pages until you reach BACK TO DASHBOARD

When you are back to Dashboard and now that you have created the consent, go to Credentials from the left panel, again click on create Credentials and select  OAuth 2.0 Client ID.

in the new link select Desktop App from the Application type menu and give it a name

After this  a new link opens up where you can also download the JSON file from a pop up window, the file you have downloaded will be used in the python script to interact with the Google Sheets or Google Drive
## (IT IS NOT CORRECT, the code will not work with this JSON file information, we need to get another JSON file that I will explain now)

# Create a Service Account and Download the JSON file
in your project control panel, again go to Credentials from left panel and in the new window select create credentials and this time select Service Account
fill the necessary information, and press Create and Continue and now you are set

now on the dashboard of your APIs and Services of your project, in Credentials tab from the left panel, you will wind Service Account created
Under Action click on the edit (pen icon)
in the new link, click on KEYS and then add Key and select JSON, as soon as you create the JSON key a file is downloaded, take that file and copy it to your preferred location

this Json file contains information that enables you to interact with the python script

# Enable the Google Sheets API:

Still within the APIs & Services > Credentials page, go to the Library section.
Search for Google Sheets API.
Click on Google Sheets API and then click Enable to activate it for your project.

# key step
Now to allow the service account access the Google Sheet we need to share the Google Sheet with the email associated with your Service account

1) open  the json file that you just downloaded, it can be opened in any editor

2) in  the json file you will find the "client email", copy that email address
3) go to your google spreadsheet , click on Share icon on the far right of the screen, Paste the email address from the JSON file and click done, you can edit different levels of access for other people as well


# with everything setup to this stage, go to the python script provided in this repository



























