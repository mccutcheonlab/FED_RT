
# Under construction👷‍♂️🚧


# RTFEDPi

![Banner Image](https://github.com/Htbibalan/FED_RT/blob/RTFEDPi/source/RTFED_Pi_Images/Cover.png)



* RTFEDPi is the Raspberry Pi variant of the classic ([RTFED](https://github.com/mccutcheonlab/FED_RT/tree/main)) and  is an open-source versatile tool for home-cage monitoring of behaviour and fiber photometry recording in mice. The RTFEDPi comes with 3 separate GUIs including RTFED(PiOS), RTFED(PiCAM) and RTFED(PiTTL). This system is developed as a home-cage setup to incorporate [FED3](https://github.com/KravitzLabDevices/FED3/wiki) units with TDT [RZ10](https://www.tdt.com/docs/hardware/rz10-lux-integrated-processor/) photometry processor for TTL-locked brain recording or to couple with USB cameras to capture event-triggered videos of behaviour.


# RTFED(PiOS)
RTFED(PiOS) can be used to remotely monitor feeding behaviour and other interactions made by mice on FED3, the data is automatically transferred to a Google spreadsheet where you can view it or define alarm notification using the Google Apps Scripts. Using the RTFEDPiOS you can also change the Mode of your FED3s without the hassle of poking one by one! However, if you are just aiming for monitoring feeding behaviour, we recommend using the basic([RTFED](https://github.com/mccutcheonlab/FED_RT/tree/main)) on Windows. 
![RTFED_PiOS](https://github.com/Htbibalan/FED_RT/blob/RTFEDPi/source/RTFED_Pi_Images/RTFED_Pi.png)


# RTFED(PiCAM)
RTFED(PiCAM) is an additional feature to the basic RTFED where you can enhance your behavioural studies by having event-triggered video recording. Primarily the RTFED(PiCAM) can record videos of mice using common USB cameras after taking Pellets, making Left or Right pokes or a combination of All of these events. Videos are limited to 30 sec length to capture only relevant behaviours while saving storage space, in this configuration, e.g. after taking a pellet, the GUI records the behaviour for 30 sec, if another pellet is taken within this 30 sec, it keeps recording for an extra 30 sec until no more pellet is taken.
![RTFED_PiCAM](https://github.com/Htbibalan/FED_RT/blob/RTFEDPi/source/RTFED_Pi_Images/RTFED(PiCAM).png)

# RTFED(PiTTL)
The TTL station of RTFED logs behavioural events made on FED3 devices and transmit them to the TDT RZ10 processors as TTL pulses. This features enables you to study event-locked signals in your experiments. However the PiTTL version does not send data online to reduce any processing load that might delay the rapid TTL puls transmission.

![RTFED_PiTTL](https://github.com/Htbibalan/HOME_PHOTOMETRY/blob/main/source/RTFED(PiTTL).png)


🚧🚧🚧🚧🚧🚧🚧🚧🚧🚧🚧🚧🚧🚧🚧🚧🚧🚧






# DOWNLOAD THE [RTFED_GUI.ZIP](https://github.com/Htbibalan/FED_RT/blob/main/source/) and run the RTFED.exe from /dist.
## The first time you run the RTFED.exe file you might face a security error,  to fix it, right click on the RTFED icon and go to properties, under the General tab you will find an Unblock option.
![EXE](https://github.com/Htbibalan/FED_RT/blob/main/source/Images/exe_security.png)
## If your IT Security issues persist, you can run the code under the hood by running the RTFED.py or the notebook RTFED.ipynb file from ../scripts/ folder, but you need to make sure that you have installed the packages on your environment, to find more information, please look at the Extra section at the bottom of this page.

# Step by step instructions for setting up RTFED
## Step -1: Update FED3 library with NEW FILES and flash the board
The process of  flashing FED3 is explained in detail on the original [FED3 repository](https://github.com/KravitzLabDevices/FED3_library), the only process you need to follow is to go to your Arduino library folder, find the FED3 library and in folder **/src** replace the FED3.h and FED3.cpp files with files provided here [RTFED_Library](https://github.com/Htbibalan/FED_RT/tree/main/source/FED3_Library/RTT).

***How to find my Arduino Library folder?***

It depends on your arduino installation settings, for example on my computer FED library is located in **C:\Arduino_lib\libraries\FED3\src** or on a Mac it is located in **/Users/your_user_name/Documents/Arduino/libraries** but the easiest way to find it is to go to File menu in your Arduino IDE and then select Preference, there you will find the pathway to your libraries.

![Arduino_0](https://github.com/Htbibalan/FED_RT/blob/main/source/Images/Arduino_lib_finding_0.png)
![Arduino_1](https://github.com/Htbibalan/FED_RT/blob/main/source/Images/Arduino_lib_finding_1.png)


After replacing the files,  connect your FED3 to your computer(**Not via the charging port rather use the one on the feather board inside the FED body**), put it on boot loader mode(Double-press the tiny button on feather board) and flash it just as explained in the original FED3 repository. 
![FED_BOOT](https://github.com/Htbibalan/FED_RT/blob/main/source/Images/FED_BOOT.png)
*Use the port indicated on the image to flash your FED otherwise your computer won't detect any device*



**Note**: You should remove the initial files including FED3.h and FED3.cpp and replace them with update files, you can save those files in a safe place in case you want to revert the changes later*

# You are recommended to also flash your board with a new "Classic_FED3_Bandits.ino" file available [here](https://github.com/Htbibalan/FED_RT/tree/main/source/FED3_Library/RTFED/), this file includes Closed_economy_PR2, DetBandit, Bandit8020 and ProbReversal modes in addition to previous modes included in original ClassicFED3.

**IMPORTANT Notes** 
There are some changes in this new update of library
1) When the device fails to deliver a pellet, it will just try 5 times in "Jam clearing" state and then stops clearing the jam  
2) As soon as the JAM is logged, the device is frozen and does not log any new activity, however it will just display the time when jamming happened on the screen.
3) The baud rate is set at 115200 to enable FED3 to log events with millisecond resolution 
4) These changes are not necessary to establish the remote data acquisition and one can try to increase the number of motor turns to clear a jam

# Hint
![RTFED_FLASHED](https://github.com/Htbibalan/FED_RT/blob/main/source/Images/RTFED_DISPLAY.jpg)
To make sure you have properly flashed your FED3 with RTFED library, check the screen of your FED3 unit, it should display RTT to the left of the battery icon.


# Step 0: Create a Google spreadsheet in your Google Drive, we will get back to it later

# Step 1: Create a project
To automatically send data from a local script to a specific Google Spreadsheet we need to get Google Service Account credentials which enables your python script to authenticate as a specific account without needing user interaction each time.


1) Go to this [link](https://console.cloud.google.com/projectcreate) to create a new project on you Google Cloud Console, as shown on  the screenshot, assign a name to it and press create.
![create_project](https://github.com/Htbibalan/FED_RT/blob/main/source/Images/project_create_1.png)

As soon as you create the project you will be prompted to project control panel, if not see notifications on the right corner bell, click on the notification icon and click on the last notification which says "project is created".

![notification](https://github.com/Htbibalan/FED_RT/blob/main/source/Images/notification_3.png)

# Step 2: Set up Service Account Credentials (Get JSON file)
Once in the control panel of your project, form the left side panel go to API and Services and then select Library.

![Control_panel](https://github.com/Htbibalan/FED_RT/blob/main/source/Images/Project_CONTROLPANEL.png)

A new link will open in the search bar look for Google Drive API.
Select the Google Drive API (probably the first item) and then ENABLE it. It will open a new link where you can control parameters of your Google Drive API.

![API_SEARCH](https://github.com/Htbibalan/FED_RT/blob/main/source/Images/API_LIB_Search_5.png)
![API_ENABLE](https://github.com/Htbibalan/FED_RT/blob/main/source/Images/select_google_drive_API_ENABLE_6.png)



After enabling your Google Drive API you will be prompted back to APIs and services, click on Credentials in the left panel menu and then select **+ CREATE CREDENTIALS** and from the menu select **Service Account**
![API_CONTROL_PANEL](https://github.com/Htbibalan/FED_RT/blob/main/source/Images/API_CONTROL_PANEL.png)
![API_SERVICE_ACOUNT](https://github.com/Htbibalan/FED_RT/blob/main/source/Images/API_CREDENTIAL_SERVICE_ACOUNT_Arrow.png)


Enter a service account name(choose your preferred name) and Service ID will be filled automatically,  then press Create and Continue or you can optionally add more users to your project or just press DONE (You can manage it later if needed)
![API_SERVICE_ACOUNT](https://github.com/Htbibalan/FED_RT/blob/main/source/Images/API_SERVICE_NAME_TEST.png)


Now on the dashboard of your APIs and Services of your project, in Credentials tab from the left panel, you will find Service Account created. Under **Action** click on the edit icon (pen icon)
![API_SERVICE_ACOUNT](https://github.com/Htbibalan/FED_RT/blob/main/source/Images/API_KEY_CREATE.png)

Click on KEYS 
![PRESS_KEY](https://github.com/Htbibalan/FED_RT/blob/main/source/Images/Press_KEY.png)

Now click on ADD KEY and then Create Key and then select JSON file.

![JSON](https://github.com/Htbibalan/FED_RT/blob/main/source/Images/API_KEY_JSON.png)

As soon as you create the JSON key a file is downloaded, take that file and copy it to your preferred location(e.g. where your python script or project folder is located on your computer), we will use this file location in the python script. This JSON file contains information that enables you to interact with the python script and spreadsheet.

# Step 3: Enable the Google Sheets API

On the APIs & Services > Credentials page, go to the Library section and search for Google Sheets API.
![API_SEARCH](https://github.com/Htbibalan/FED_RT/blob/main/source/Images/API_GOOGLE_SHEET_LIBRARY_WINDOW_arrow.png)


![API_SEARCH](https://github.com/Htbibalan/FED_RT/blob/main/source/Images/API_LIB_Search_5.png)

Select Google Sheets API and then click Enable to activate it for your project.

![GOOGLESHEETS_API](https://github.com/Htbibalan/FED_RT/blob/main/source/Images/Activate_GOOGLE_SHEETS_API.png)

# Step 4: Critical step - get the email address from JSON file
Now to allow the Service Account access the Google spreadsheet we need to share the Google spreadsheet with the email associated with your Service account (Go to the JSON file)

1) Open  the JSON file that you just downloaded, it can be opened in any editor(like notepad or VSCode).
2) In  the JSON file you will find the "client email", copy that email address(the quotation mark is not needed)
3) Go to your Google spreadsheet on your Google drive , click on Share icon on the far right of the screen, Paste the email address from the JSON file, set General Access to "Anyone with the link" and click done, you can edit different levels of access for other people as well (For example View only or Editor).

# Step 5: Setup the Alarm system(email notification for events)
1) While in your Google Spreadsheet, from menu Extensions, select Apps Script and clear any existing code.
 ![App_script](https://github.com/Htbibalan/FED_RT/blob/main/source/Images/app_script.png)


2) Paste the code below, make necessary changes described below in **Critical sub-step** and then press the **"save"** icon. 

### Critical sub-step: 
**After flashing your FED3 using the .cpp and .h files provided in this repository, you will have two extra columns in your FED files for Humidity and Temperature, those columns will remain blank if you do not have those sensors installed on your FED units, however this will not interfere with your data logging, just make sure correct column number are passed to the Apps Script code**

 **Also to receive a email alerts for JAM and Pellets Consumed, you need to add your own email address to the last snippet of the code where it indicates: var emailAddress. You can also change the variable ***var pelletThreshold*** to set a threshold in case you want to receive emails when certain amounts of pellets are consumed by mice**



        function checkForJam() {
        var spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
        var sheets = spreadsheet.getSheets(); // Get all sheets in the spreadsheet
        var eventColumn = 10; // Column J where the "Event" data is located
        var deviceColumn = 6; // Column F where the device number is located
        var timestampColumn = 1; // Column A where the timestamp is located
        var pelletCountColumn = 14; // Column N where the Pellet_Count data is located
        var pelletThreshold = 3; // Threshold for Pellet_Count

        var scriptProperties = PropertiesService.getScriptProperties();

        for (var i = 0; i < sheets.length; i++) {
            var sheet = sheets[i];
            var lastRow = sheet.getLastRow();
            
            if (lastRow > 0) { // Check if the sheet has any data
            var event = sheet.getRange(lastRow, eventColumn).getValue();
            var deviceNumber = sheet.getRange(lastRow, deviceColumn).getValue();
            var timestamp = sheet.getRange(lastRow, timestampColumn).getValue();
            var pelletCount = sheet.getRange(lastRow, pelletCountColumn).getValue();
            
            // Create unique keys for JAM and Pellet Count alerts
            var jamEventKey = "JAM_" + sheet.getName() + "_" + deviceNumber + "_" + timestamp;
            var pelletEventKey = "PELLET_" + sheet.getName() + "_" + deviceNumber;

            // Check and send JAM alert
            var lastProcessedJamEvent = scriptProperties.getProperty(jamEventKey);
            if (event === "JAM" && lastProcessedJamEvent !== jamEventKey) {
                sendJamAlert(sheet.getName(), lastRow, event, deviceNumber);
                scriptProperties.setProperty(jamEventKey, jamEventKey); // Mark JAM event as processed
            }

            // Check and send Pellet Count alert
            var lastProcessedPelletEvent = scriptProperties.getProperty(pelletEventKey);
            if (pelletCount >= pelletThreshold && lastProcessedPelletEvent !== pelletEventKey) {
                sendPelletAlert(sheet.getName(), deviceNumber, pelletCount);
                scriptProperties.setProperty(pelletEventKey, pelletEventKey); // Mark Pellet Count event as processed
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

        function sendPelletAlert(sheetName, deviceNumber, pelletCount) {
        var emailAddress = "Add_your_email_address"; // Replace with your email address
        var subject = "FED3 Device Alert: Pellet Threshold Reached";
        var message = "A FED unit has reached the pellet count threshold.\n\n"
                    + "Details:\n"
                    + "Sheet: " + sheetName + "\n"
                    + "Device Number: " + deviceNumber + "\n"
                    + "Pellet Count: " + pelletCount + "\n"
                    + "Please review the data or refill pellets as needed.";
        
        MailApp.sendEmail(emailAddress, subject, message);
        }


 ![Apps_script_email_address](https://github.com/Htbibalan/FED_RT/blob/main/source/Images/Apps_script_email.png)
 *As shown in the image, just change the email address in the "var emailAdress" and leave the emailAddress parameter in the function unchanged*


3) **To activate the Alarm email**,  in the Apps Script control panel, from the left panel menu, select **Triggers** and then right bottom corner select **+ Add Trigger** 

 ![App_script](https://github.com/Htbibalan/FED_RT/blob/main/source/Images/trigger_APPS_SCRIPT.png)

 Set the settings according to the screenshot below:

  ![Trigger_setup](https://github.com/Htbibalan/FED_RT/blob/main/source/Images/Trigger_Setup.png)

**After saving the trigger, a warning will show up -- image below**
 ![Trigger_setup](https://github.com/Htbibalan/FED_RT/blob/main/source/Images/GOOGLE_WARNING.png)


**Click on Advanced, then click on Go to your project then click on Allow**

--------------------------------------------------------------------------------------------------------------------


 **IMPORTANT NOTE**:
 The RTFED ignores the timestamp data coming from FEDs and gets the timestamp from the mother computer, which means that all the FEDs connected to the main computer will be synchronized.

# Extra (For expert users who want to make changes in the codes)
You can use either the [.yml file](https://github.com/Htbibalan/FED_RT/tree/main/source/ENV_FILES) to create a separate environment for your RTFED python code, or use the requirement.txt file from the same folder to get the required  python packages. Follow the instructions on [ANACONDA_CHEAT_SHEET](https://docs.conda.io/projects/conda/en/4.6.0/_downloads/52a95608c49671267e40c689e0bc00ca/conda-cheatsheet.pdf), but basically download the above mentioned files and move them to your anaconda environments directory, open your anaconda terminal and navigate to to the directory where the RTFED.yml is located and run the command below:

                conda env create -f RTFED.yml

Alternatively you can use the requirement.txt file to either update packages in your base/current environment or making an env from the scratch,simply navigate to the directory where you have the requirements.txt located, and run the following command:

                pip install -r requirements.txt


# License
This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

# Author of this repository
Hamid Taghipourbibalan, Ph.D. student at [McCutcheon_lab](https://www.mccutcheonlab.com/) at UiT The Arctic University of Norway.




















