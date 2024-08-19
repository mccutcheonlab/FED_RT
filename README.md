# REALTIME_REMOTE_FED(RTFED)

![Banner Image](https://github.com/Htbibalan/FED_RT/blob/main/source/Images/diagram.png)
### What is RTFED?
**RTFED** is a software update to the open-source automated feeding/operant_reward machine [FED3](https://github.com/KravitzLabDevices/FED3/wiki). This update enables you to collect data from FED3 online and remotely without needing any additional hardware change.(e.g. directly to a Google spreadsheet instead of writing to the SD card). Moreover here I share a walkthrough of the process of incorporating a Google Apps Script with your spreadsheet to send you an alarm email in case your FED3 fails to deliver a pellet (e.g. jamming happens)

*Since you need to have your FED3 connected to a computer via a USB cable all the time, this solution works best for labs who do not place the FED3 inside the mouse cage or can protect the FED3 and cable from the mice.*

*So far it has been tested on Windows and Mac and it works fine on both operating systems.*

# Step by step instructions for setting up RTFED
## Step -1: Update FED3 library with NEW FILES and flash the board
The process of  flashing FED3 is explained in detail on the original [FED3 repository](https://github.com/KravitzLabDevices/FED3_library), the only process you need to follow is to go to your Arduino library folder, find the FED3 library and in folder **/src** replace the FED3.h and FED3.cpp files with files provided here [FED3_Library](https://github.com/Htbibalan/FED_RT/tree/main/source/FED3_Library). 
After replacing the files,  connect your FED3 to your computer, put it on boot loader mode and flash it just as explained in the original FED3 repository. 

[people should click on the file and then they can download in the next link
]
[you should remove the initial files including FED3.h and FED3.cpp and replace them with update files, you can save those files in a safe place in case you want to revert the settings]

Optional: You can also flash your board with a new "ClassicFED3.ino" file available [here](https://github.com/Htbibalan/FED_RT/tree/main/source/FED3_Library/ClassicFED3), this file includes Closed_economy mode in addition to previous modes included in original ClassicFED3.

**note: There are several changes in this new update of library(this topic is under_construction)**
1) This library was intitally developed to trigger an alarm LED on FEDs.


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

## Step 3: Enable the Google Sheets API

Still within the APIs & Services > Credentials page, go to the Library section and search for Google Sheets API.

![API_SEARCH](https://github.com/Htbibalan/FED_RT/blob/main/source/Images/API_LIB_Search_5.png)

Select Google Sheets API and then click Enable to activate it for your project.

![GOOGLESHEETS_API](https://github.com/Htbibalan/FED_RT/blob/main/source/Images/Activate_GOOGLE_SHEETS_API.png)

## Step 4: Critical step - get the email address from JSON file
Now to allow the Service Account access the Google spreadsheet we need to share the Google spreadsheet with the email associated with your Service account (Go to the JSON file)

1) Open  the JSON file that you just downloaded, it can be opened in any editor(like notepad or VSCode).
2) In  the JSON file you will find the "client email", copy that email address(the quotation mark is not needed)
3) Go to your Google spreadsheet on your Google drive , click on Share icon on the far right of the screen, Paste the email address from the JSON file and click done, you can edit different levels of access for other people as well.

## Step 5: Setup the JAM Alarm system(email notification for events)
1) While in your Google Spreadsheet, from menu Extensions, select Apps Script and clear any existing code.
 ![App_script](https://github.com/Htbibalan/FED_RT/blob/main/source/Images/app_script.png)


2) Paste the code below and press the "save" icon. But There are a few changes to make based on your FED file. If you do not have Humidity and Temp sensors, the column number for "event" and "device number" will be different, replace it accordingly. Also to receive a JAM alert, you need to add your own email address to the last snipped of the code where it says: var emailAddress



            function checkForJam() {
            var spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
            var sheets = spreadsheet.getSheets(); // Get all sheets in the spreadsheet
            var eventColumn = 10; // Column J where the "Event" data is located
            var deviceColumn = 6; // Column F where the device number is located
            var timestampColumn = 1; // Column A where the timestamp is located

            var scriptProperties = PropertiesService.getScriptProperties();

            for (var i = 0; i < sheets.length; i++) {
                var sheet = sheets[i];
                var lastRow = sheet.getLastRow();
                
                if (lastRow > 0) { // Check if the sheet has any data
                var event = sheet.getRange(lastRow, eventColumn).getValue();
                var deviceNumber = sheet.getRange(lastRow, deviceColumn).getValue();
                var timestamp = sheet.getRange(lastRow, timestampColumn).getValue();
                
                // Create a unique key for this event
                var eventKey = sheet.getName() + "_" + deviceNumber + "_" + timestamp;

                // Check if this event has already been processed
                var lastProcessedEvent = scriptProperties.getProperty(eventKey);
                
                if (event === "JAM" && lastProcessedEvent !== eventKey) {
                    sendJamAlert(sheet.getName(), lastRow, event, deviceNumber);
                    scriptProperties.setProperty(eventKey, eventKey); // Store the event as processed
                }
                }
            }
            }

            function sendJamAlert(sheetName, row, event, deviceNumber) {
            var emailAddress = "Add_your_email_address"; // Replace with your email address
            var subject = "FED3 Device Alert: JAM Detected";
            var message = "A FED unit has failed.\n\n"
                        + "Details:\n"
                        + "Sheet: " + sheetName + "\n"
                        + "Row: " + row + "\n"
                        + "Device Number: " + deviceNumber + "\n"
                        + "Event: " + event + "\n"
                        + "Please go and check your device.";

            MailApp.sendEmail(emailAddress, subject, message);
            }


3) In the Apps Script control panel, from the left panel menu, select **Triggers**

 ![App_script](https://github.com/Htbibalan/FED_RT/blob/main/source/Images/trigger_APPS_SCRIPT.png)

 Set the settings according to the screenshot below:

  ![Trigger_setup](https://github.com/Htbibalan/FED_RT/blob/main/source/Images/Trigger_Setup.png)



## Step 6: Open your python IDE(e.g. Jupyter lab) and copy the code from this repository
 With everything setup to this stage, go to the python script provided here [RTFED](https://github.com/Htbibalan/FED_RT/blob/main/scripts/RTFED.ipynb) , install the necessary packages and libraries- section 1 of the script and then before running the code, replace the variables according to your own spreadsheet and file path.

1) Replace the CREDS_FILE directory with the pathway to you JSON file, also replace your own Google spreadsheet ID and if you have not installed Humidity and Temperature sensors on your FED3, also remove those column headers Temp and Humidify. Moreover you will need to change Ports based on your own Port names and number of FEDs connected to your computer.

2) To find your Google spreadsheet ID, open the spreadsheet and in the address bar, copy everything between d/.../edit as shown in the image below
 ![SHEET_ID](https://github.com/Htbibalan/FED_RT/blob/main/source/Images/SHEET_ID.png)

 Image below shows the changes you need to make in your python script:
  ![Python_sctipy](https://github.com/Htbibalan/FED_RT/blob/main/source/Images/python_script.png)

3)To find port number, open your Arduino IDE with your FED connected and switched on (you do not need to put it on boot loader mode if you have already flashed it with the library provided in my repository [FED3_Library](https://github.com/Htbibalan/FED_RT/tree/main/source/FED3_Library)). Go to Tools/Ports and there you will find port numbers.

  ![Python_sctipy](https://github.com/Htbibalan/FED_RT/blob/main/source/Images/Arduino_Port.png)

In this screenshot, 2 FEDs are connected, which means that in the python script, the user can include COM12 as well.
                
                port=["COM16","COM12"]

On Mac systems the port name is not displayed as COM but as a longer name, however you will find it through the same menu on Arduino IDE.

## Step 7: Run a test
1) Swtich on FEDs connected with a USB cable to your computer
2) Run the python script with all variables adjusted based on your own setup
3) As soon as you run the code sheets get their names from "ports" variable in the python script and are generated on your Google spreadsheet
4) Make random pokes and pellet deliveries and you should see the data being logged on the spreadsheet
5) Trigger a jamming by not letting the FED3 deliver a pellet and soon you will receive an alarm email.































