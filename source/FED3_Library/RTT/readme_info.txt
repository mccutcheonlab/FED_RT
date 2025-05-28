if you need to have more modes included in your library and then recognized by RTFED GUI, you need to adjust some snippets


   // SET_MODE:<0–15>
    } else if (line.startsWith("SET_MODE:")) {
      line.remove(0, 9); // remove "SET_MODE:"
      int mode = line.toInt();
      if (mode >= 0 && mode <= 15) {
        FEDmode = mode;
        writeFEDmode();            // Save new mode to SD
        Serial.println("MODE_SET_OK");
        delay(200);
        NVIC_SystemReset();        // Reboot into new mode
      } else {
        Serial.println("MODE_SET_FAIL");
      }


here you need to add up extra modes e.g. if you have modes 16 or 17


then update additional modes here

  display.setCursor(10, 60);
  //Text to display selected FR ratio
  if (FEDmode == 0) display.print("Mode 1");
  if (FEDmode == 1) display.print("Mode 2");
  if (FEDmode == 2) display.print("Mode 3");
  if (FEDmode == 3) display.print("Mode 4");
  if (FEDmode == 4) display.print("Mode 5");
  if (FEDmode == 5) display.print("Mode 6");
  if (FEDmode == 6) display.print("Mode 7");
  if (FEDmode == 7) display.print("Mode 8");
  if (FEDmode == 8) display.print("Mode 9");
  if (FEDmode == 9) display.print("Mode 10");
  if (FEDmode == 10) display.print("Mode 11");
  if (FEDmode == 11) display.print("Mode 12");
  if (FEDmode == 12) display.print("Mode 13");
  if (FEDmode == 13) display.print("Mode 14");
  if (FEDmode == 14) display.print("Mode 15");
  if (FEDmode == 15) display.print("Mode 16");
  DisplayMouse();
  display.clearDisplay();
  display.refresh();
}




and here


  //In classic mode we pre-specify these programs names
  if (ClassicFED3==true){
    if (FEDmode == 0) display.print("Free feeding");
    if (FEDmode == 1) display.print("FR1");
    if (FEDmode == 2) display.print("FR3");
    if (FEDmode == 3) display.print("FR5");
    if (FEDmode == 4) display.print("Progressive Ratio");
    if (FEDmode == 5) display.print("Extinction");
    if (FEDmode == 6) display.print("Light tracking");
    if (FEDmode == 7) display.print("FR1 (Reversed)");
    if (FEDmode == 8) display.print("Prog Ratio (Rev)");
    if (FEDmode == 9) display.print("Self-Stim");
    if (FEDmode == 10) display.print("Self-Stim (Rev)");
    if (FEDmode == 11) display.print("Timed feeding");
    if (FEDmode == 12) display.print("ClosedEconomy_PR2");
    if (FEDmode == 13) display.print("Probabilistic Reversal");
    if (FEDmode == 14) display.print("Bandit8020");
    if (FEDmode == 15) display.print("DetBandit");

    
    display.refresh();
  }
  





  display.setCursor(10, 60);
  //Text to display selected FR ratio
  if (FEDmode == 0) display.print("Free feeding");
  if (FEDmode == 1) display.print("FR1");
  if (FEDmode == 2) display.print("FR3");
  if (FEDmode == 3) display.print("FR5");
  if (FEDmode == 4) display.print("Progressive Ratio");
  if (FEDmode == 5) display.print("Extinction");
  if (FEDmode == 6) display.print("Light tracking");
  if (FEDmode == 7) display.print("FR1 (Reversed)");
  if (FEDmode == 8) display.print("Prog Ratio (Rev)");
  if (FEDmode == 9) display.print("Self-Stim");
  if (FEDmode == 10) display.print("Self-Stim (Rev)");
  if (FEDmode == 11) display.print("Timed feeding");
  if (FEDmode == 12) display.print("ClosedEconomy_PR1");
  if (FEDmode == 13) display.print("Probabilistic Reversal");
  if (FEDmode == 14) display.print("Bandit Task");
  if (FEDmode == 15) display.print("Deterministic Bandit");
  
  DisplayMouse();
  display.clearDisplay();
  display.refresh();
}



Optionally you can also include the new modes here and their FR values

  // Set FR based on FEDmode
  if (FEDmode == 0) FR = 0;  // free feeding
  if (FEDmode == 1) FR = 1;  // FR1 spatial tracking task
  if (FEDmode == 2) FR = 3;  // FR3
  if (FEDmode == 3) FR = 5; // FR5
  if (FEDmode == 4) FR = 99;  // Progressive Ratio
  if (FEDmode == 5) { // Extinction
    FR = 1;
    ReleaseMotor ();
    digitalWrite (MOTOR_ENABLE, LOW);  //disable motor driver and neopixels
    delay(2); //let things settle
  }
  if (FEDmode == 6) FR = 1;  // Light tracking
  if (FEDmode == 7) FR = 1; // FR1 (reversed)
  if (FEDmode == 8) FR = 1; // PR (reversed)
  if (FEDmode == 9) FR = 1; // self-stim
  if (FEDmode == 10) FR = 1; // self-stim (reversed)
  if (FEDmode == 11) FR = 1; // Timed feeding
  if (FEDmode == 12) FR = 1; // ClosedEconomy_PR1
  if (FEDmode == 13) FR = 1; // Probabilistic Reversal
  if (FEDmode == 14) FR = 1; // Bandit Task
  if (FEDmode == 15) FR = 1; // Deterministic Bandit







Finally you need to go to the GUI code and adjust this snippet and add the extra modes

        self.mode_options = [
            "0 - Free Feeding", "1 - FR1", "2 - FR3", "3 - FR5",
            "4 - Progressive Ratio", "5 - Extinction", "6 - Light Tracking",
            "7 - FR1 (Reversed)", "8 - PR (Reversed)", "9 - Self-Stim",
            "10 - Self-Stim (Reversed)", "11 - Timed Feeding", "12 - ClosedEconomy_PR2", "13 - Probabilistic Reversal", "14 - Bandit8020", "15 - DetBandit"
        ]



