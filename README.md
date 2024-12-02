# REALTIME_REMOTE_FED(RTFED)

![Banner Image](https://github.com/Htbibalan/FED_RT/blob/main/source/Images/diagram.png)
### What is RTFED?
**RTFED** is a software update to the open-source automated feeding/operant_reward machine [FED3](https://github.com/KravitzLabDevices/FED3/wiki). This update enables you to collect data from FED3 online and remotely without needing any additional hardware change.(e.g. directly to a Google spreadsheet instead of writing to the SD card). Moreover here I share a walkthrough of the process of incorporating a Google Apps Script with your spreadsheet to send you an alarm email in case your FED3 fails to deliver a pellet (e.g. jamming happens)

*Since you need to have your FED3 connected to a computer via a USB cable all the time, this solution works best for labs who do not place the FED3 inside the mouse cage or can protect the FED3 and cable from the mice.*

*So far it has been tested on Windows and Mac and it works fine on both operating systems.*

## Upgrade V2 (NOV 2024):
**RTFED now handles interruptions in your internet connection by caching the data on RAM and periodically checking the connection**

## Upgrade V3 (Dec 2024)
**RTFED now comes with a GUI (zip file in /source), dynamically detects FED3 devices connected to your computer. Plug and Play!** 

# Step by step instructions for setting up RTFED
## Step -1: Update FED3 library with NEW FILES and flash the board
The process of  flashing FED3 is explained in detail on the original [FED3 repository](https://github.com/KravitzLabDevices/FED3_library), the only process you need to follow is to go to your Arduino library folder, find the FED3 library and in folder **/src** replace the FED3.h and FED3.cpp files with files provided here [RTFED_Library](https://github.com/Htbibalan/FED_RT/tree/main/source/FED3_Library/RTFED).

***How to find my Arduino Library folder?***

It depends on your arduino installation settings, for example on my computer FED library is located in **C:\Arduino_lib\libraries\FED3\src** or on a Mac it is located in **/Users/your_user_name/Documents/Arduino/libraries** but the easiest way to find it is to go to File menu in your Arduino IDE and then select Preference, there you will find the pathway to your libraries.

![Arduino_0](https://github.com/Htbibalan/FED_RT/blob/main/source/Images/Arduino_lib_finding_0.png)
![Arduino_1](https://github.com/Htbibalan/FED_RT/blob/main/source/Images/Arduino_lib_finding_1.png)


After replacing the files,  connect your FED3 to your computer(**Not via the charging port rather use the one on the feather board inside the FED body**), put it on boot loader mode(Double-press the tiny button on feather board) and flash it just as explained in the original FED3 repository. 
![FED_BOOT](https://github.com/Htbibalan/FED_RT/blob/main/source/Images/FED_BOOT.png)
*Use the port indicated on the image to flash your FED otherwise your computer won't detect any device*



**Note**: You should remove the initial files including FED3.h and FED3.cpp and replace them with update files, you can save those files in a safe place in case you want to revert the changes later*

Optional: You can also flash your board with a new "ClassicFED3.ino" file available [here](https://github.com/Htbibalan/FED_RT/tree/main/source/FED3_Library/ClassicFED3), this file includes Closed_economy mode in addition to previous modes included in original ClassicFED3.

** **IMPORTANT** notes: There are some changes in this new update of library**
1) This library was initially developed to trigger an alarm LED on FEDs when the device is jammed, in this update FED will make 2 Beeps every 10 sec when it is jammed until it is restarted (this was meant to notify people in the animal facility about the jamming)
2) When the device fails to deliver a pellet, it will just try 3 times in "Jam clearing" state and then stops clearing the jam, the sound alarm goes off and a JAM event is logged,  
3) As soon as the JAM is logged, the device is frozen and does not log any new activity, however it will just display the time when jamming happened on the screen
4) The baud rate is set at 115200 to enable FED3 to log events with millisecond resolution 
5) These changes are not necessary to establish the remote data acquisition and one can try to increase the number of motor turns to clear a jam or shut down the beeping alarm. 



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

# Step 5: Setup the JAM Alarm system(email notification for events)
1) While in your Google Spreadsheet, from menu Extensions, select Apps Script and clear any existing code.
 ![App_script](https://github.com/Htbibalan/FED_RT/blob/main/source/Images/app_script.png)


2) Paste the code below, make necessary changes described below in **Critical sub-step** and then press the **"save"** icon. 

### Critical sub-step: 
**Afer flashing your FED3 using the .cpp and .h files provided in this repository, you will have two extra columns in your FED files for Humidity and Temperature, those columns will remain blank if you do not have those sensors installed on your FED units, however this will not interfere with your data logging**

 **Also to receive a JAM alert, you need to add your own email address to the last snipped of the code where it says: var emailAddress**



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

 ![Apps_script_email_address](https://github.com/Htbibalan/FED_RT/blob/main/source/Images/Apps_script_email.png)
 *As shown in the image, just change the email address in the "var emailAdress" and leave the emailAddress parameter in the function unchanged*


3) **To activate the Alarm email**,  in the Apps Script control panel, from the left panel menu, select **Triggers** and then right bottom corner select **+ Add Trigger** 

 ![App_script](https://github.com/Htbibalan/FED_RT/blob/main/source/Images/trigger_APPS_SCRIPT.png)

 Set the settings according to the screenshot below:

  ![Trigger_setup](https://github.com/Htbibalan/FED_RT/blob/main/source/Images/Trigger_Setup.png)

**After saving the trigger, a warning will show up -- image below**
 ![Trigger_setup](https://github.com/Htbibalan/FED_RT/blob/main/source/Images/GOOGLE_WARNING.png)


**Click on Advanced, then click on Go to your project then click on Allow**


# Step 6: **THIS STEP IS NO LONGER NEEDED SINCE YOU ARE USING THE GUI and GUI detects your ports automatically and asks for JSON file and spreadsheet ID** Open your python IDE(e.g. Jupyter lab) and copy the code from this repository
 With everything setup to this stage, make a new notebook in your jupyter lab and get the code from the python script provided here [RTFED](https://github.com/Htbibalan/FED_RT/blob/main/scripts/RTFED.ipynb) and copy the script and paste it in your notebook.
 Install the necessary packages and libraries- section 1 of the script and then **before running the code**, replace the variables according to your own spreadsheet and file path.

 Image below shows the changes you need to make in your python script, you will find the details below:
  ![Python_script](https://github.com/Htbibalan/FED_RT/blob/main/source/Images/python_script_number.png)
 
 1) If you have not installed Humidity and Temperature sensors on your FED3, remove those column headers Temperature and Humidity. 

2) Replace the CREDS_FILE directory with the pathway to your JSON file, 

3) Also replace your own Google spreadsheet ID

3-1)To find your Google spreadsheet ID, open the spreadsheet and in the address bar, copy everything between d/.../edit as shown in the image below, excluding the slashes.

 ![SHEET_ID](https://github.com/Htbibalan/FED_RT/blob/main/source/Images/SHEET_ID.png)

4)Moreover you will need to change Ports based on your own Port names and number of FEDs connected to your computer.

4-1)To find port number, open your Arduino IDE with your FED connected and switched on (you do not need to put it on boot loader mode if you have already flashed it with the library provided in my repository [FED3_Library](https://github.com/Htbibalan/FED_RT/tree/main/source/FED3_Library)). Go to Tools/Ports and there you will find port numbers.

  ![arduino_port_find](https://github.com/Htbibalan/FED_RT/blob/main/source/Images/Arduino_Port.png)

In this screenshot, 2 FEDs are connected, which means that in the python script, the user can include COM12 as well.
                
                port=["COM16","COM12"]

On Mac systems the port name is not displayed as COM but as a longer name, however you will find it through the same menu on Arduino IDE.(Image below - copy the highlighted part)

 ![MAC](https://github.com/Htbibalan/FED_RT/blob/main/source/Images/MAC.png)


 **IMPORTANT NOTE**:
 The python script ignores the timestamp data coming from FEDs and gets the timestamp from the mother computer, which means that all the FEDs connected to the main computer are synchronized

# Step 7: Run a test
1) Switch on FEDs connected with a USB cable to your computer
2) Run the python script with all variables adjusted based on your own setup
3) As soon as you run the code, new sheets will be generated and they get the sheet name from the Ports variable
4) Make random pokes and pellet deliveries and you should see the data being logged on the spreadsheet
5) Trigger a jamming by not letting the FED3 deliver a pellet and soon you will receive an alarm email.


# Extra (For expert users)
You can use either the [.yml file](https://github.com/Htbibalan/FED_RT/tree/main/source/ENV_FILES) to create a separate environment for your RTFED python code, or use the requirement.txt file from the same folder to get the required  python packages. Follow the instructions on [ANACONDA_CHEAT_SHEET](https://docs.conda.io/projects/conda/en/4.6.0/_downloads/52a95608c49671267e40c689e0bc00ca/conda-cheatsheet.pdf), but basically download the above mentioned files and move them to your anaconda environments directory, open your anaconda terminal and navigate to to the directory where the RTFED.yml is located and run the command below:

                conda env create -f RTFED.yml

Alternatively you can use the requirement.txt file to either update packages in your base/current environment or making an env from the scratch,simply navigate to the directory where you have the requirements.txt located, and run the following command:

                pip install -r requirements.txt


Also you can find the .py file of the RTFED python script [HERE](https://github.com/Htbibalan/FED_RT/tree/main/scripts/RTFED_V1.py)
# License

        MIT License

        Copyright (c) 2024 Htbibalan

        Permission is hereby granted, free of charge, to any person obtaining a copy
        of this software and associated documentation files (the "Software"), to deal
        in the Software without restriction, including without limitation the rights
        to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
        copies of the Software, and to permit persons to whom the Software is
        furnished to do so, subject to the following conditions:

        The above copyright notice and this permission notice shall be included in all
        copies or substantial portions of the Software.

        THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
        IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
        FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
        AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
        LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
        OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
        SOFTWARE.

# Author
Hamid Taghipourbibalan, Ph.D. student at [McCutcheon_lab](https://www.mccutcheonlab.com/) at UiT The Arctic University of Norway.




















