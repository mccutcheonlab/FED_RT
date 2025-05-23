/*
  Adding Modes 0–15 (Classic + ProbRev + Bandit + Deterministic Bandit) to FED3 edited May 23 2025 by Hamid Taghipourbibalan
*/

#include <FED3.h>
String sketch = "Classic_with_ProbRev";
FED3 fed3(sketch);

// Variables for PR tasks (mode 4, 8, 12)
int poke_num = 0;
int pokes_required = 1;
int pellets_in_current_block = 0;
unsigned long poketime = 0;
int resetInterval = 1800; // seconds without a poke to reset (for mode 12)

// Variables for Mode 13: Probabilistic Reversal Task
int probability = 80;
int trialsToSwitch = 10;
int counter = 1;
int trialTimeout = 5;

// Variables for Mode 14: Bandit Task
int pellet_counter = 0;
int timeoutIncorrect = 10;
int probs[2] = {80, 20};
int new_prob = 0;

// Variables for Mode 15: Deterministic Bandit Task
int pellet_counter_det = 0;
int deterministicPelletsToSwitch = 20;
bool rewardLeft = true;

void setup() {
  fed3.ClassicFED3 = true;
  fed3.begin();
}

void loop() {
  // Mode 0: Free feed
  if (fed3.FEDmode == 0) {
    fed3.sessiontype = "Free_feed";
    fed3.DisplayPokes = false;
    fed3.UpdateDisplay();
    fed3.Feed();
    fed3.Timeout(5);
  }
  // Modes 1–3: FR1, FR3, FR5
  else if (fed3.FEDmode == 1 || fed3.FEDmode == 2 || fed3.FEDmode == 3) {
    if (fed3.FEDmode == 1)   fed3.sessiontype = "FR1";
    else if (fed3.FEDmode == 2) fed3.sessiontype = "FR3";
    else                      fed3.sessiontype = "FR5";
    if (fed3.Left) {
      fed3.logLeftPoke();
      if (fed3.LeftCount % fed3.FR == 0) {
        fed3.ConditionedStimulus();
        fed3.Feed();
      }
    }
    if (fed3.Right) fed3.logRightPoke();
  }
  // Mode 4: Progressive Ratio
  else if (fed3.FEDmode == 4) {
    fed3.sessiontype = "ProgRatio";
    if (fed3.Left) {
      fed3.logLeftPoke();
      fed3.Click();
      poke_num++;
      if (poke_num == pokes_required) {
        fed3.ConditionedStimulus();
        fed3.Feed();
        pokes_required = round((5 * exp((fed3.PelletCount + 1) * 0.2)) - 5);
        fed3.FR = pokes_required;
        poke_num = 0;
      }
    }
    if (fed3.Right) fed3.logRightPoke();
  }
  // Mode 5: Extinction
  else if (fed3.FEDmode == 5) {
    fed3.sessiontype = "Extinct";
    if (fed3.Left) {
      fed3.logLeftPoke();
      fed3.ConditionedStimulus();
    }
    if (fed3.Right) fed3.logRightPoke();
  }
  // Mode 6: Light Tracking
  else if (fed3.FEDmode == 6) {
    fed3.sessiontype = "Light Trk";
    fed3.disableSleep();
    if (fed3.activePoke == 1) {
      fed3.leftPokePixel(5,5,5,0);
      if (fed3.Left) {
        fed3.logLeftPoke();
        fed3.ConditionedStimulus();
        fed3.Feed();
        fed3.randomizeActivePoke(3);
      }
      if (fed3.Right) fed3.logRightPoke();
    } else {
      fed3.rightPokePixel(5,5,5,0);
      if (fed3.Right) {
        fed3.logRightPoke();
        fed3.ConditionedStimulus();
        fed3.Feed();
        fed3.randomizeActivePoke(3);
      }
      if (fed3.Left) fed3.logLeftPoke();
    }
  }
  // Mode 7: FR1, Right only
  else if (fed3.FEDmode == 7) {
    fed3.sessiontype = "FR1_R";
    fed3.activePoke = 0;
    if (fed3.Left)  fed3.logLeftPoke();
    if (fed3.Right) {
      fed3.logRightPoke();
      fed3.ConditionedStimulus();
      fed3.Feed();
    }
  }
  // Mode 8: Progressive Ratio, Right only
  else if (fed3.FEDmode == 8) {
    fed3.sessiontype = "PR_R";
    fed3.activePoke = 0;
    if (fed3.Right) {
      fed3.logRightPoke();
      poke_num++;
      if (poke_num == pokes_required) {
        fed3.ConditionedStimulus();
        fed3.Feed();
        pokes_required = round((5 * exp((fed3.PelletCount + 1) * 0.2)) - 5);
        fed3.FR = pokes_required;
        poke_num = 0;
      } else {
        fed3.Click();
      }
    }
    if (fed3.Left) fed3.logLeftPoke();
  }
  // Mode 9: OptoStim
  else if (fed3.FEDmode == 9) {
    fed3.sessiontype = "OptoStim";
    if (fed3.Left) {
      fed3.logLeftPoke();
      fed3.ConditionedStimulus();
      fed3.BNC(25, 20);
    }
    if (fed3.Right) fed3.logRightPoke();
  }
  // Mode 10: OptoStim, Right only
  else if (fed3.FEDmode == 10) {
    fed3.sessiontype = "OptoStim_R";
    fed3.activePoke = 0;
    if (fed3.Right) {
      fed3.logRightPoke();
      fed3.ConditionedStimulus();
      fed3.BNC(25, 20);
    }
    if (fed3.Left) fed3.logLeftPoke();
  }
  // Mode 11: Timed access
  else if (fed3.FEDmode == 11) {
    fed3.sessiontype = "Timed";
    fed3.DisplayPokes = false;
    fed3.DisplayTimed = true;
    fed3.UpdateDisplay();
    if (fed3.currentHour >= fed3.timedStart && fed3.currentHour < fed3.timedEnd) {
      fed3.Feed();
      fed3.Timeout(5);
    }
  }
  // Mode 12: Closed Economy PR1
  else if (fed3.FEDmode == 12) {
    fed3.sessiontype = "ClEco_PR1";
    checkReset();
    if (fed3.Left) {
      fed3.logLeftPoke();
      poke_num++;
      poketime = fed3.unixtime;
      serialoutput();
      if (poke_num == pokes_required) {
        fed3.ConditionedStimulus();
        pellets_in_current_block++;
        fed3.BlockPelletCount = pellets_in_current_block;
        fed3.Feed();
        pokes_required += 2;
        fed3.FR = pokes_required;
        poke_num = 0;
      }
    }
    if (fed3.Right) fed3.logRightPoke();
  }
  // Mode 13: Probabilistic Reversal
  else if (fed3.FEDmode == 13) {
    fed3.sessiontype = "ProbRev";
    fed3.disableSleep();
    if (counter == ((trialsToSwitch * 2) + 1)) counter = 1;
    fed3.activePoke = (counter <= trialsToSwitch) ? 1 : 0;
    // Four possible poke scenarios:
    if (fed3.activePoke == 1 && fed3.Left) {
      fed3.logLeftPoke();
      if (random(100) < probability) {
        fed3.ConditionedStimulus(); fed3.Feed();
      } else {
        fed3.Tone(4000, 200);
      }
      counter++; fed3.Timeout(trialTimeout);
    }
    if (fed3.activePoke == 1 && fed3.Right) {
      fed3.logRightPoke();
      if (random(100) > probability) {
        fed3.ConditionedStimulus(); fed3.Feed();
      } else {
        fed3.Tone(4000, 200);
      }
      counter++; fed3.Timeout(trialTimeout);
    }
    if (fed3.activePoke == 0 && fed3.Left) {
      fed3.logLeftPoke();
      if (random(100) > probability) {
        fed3.ConditionedStimulus(); fed3.Feed();
      } else {
        fed3.Tone(4000, 200);
      }
      counter++; fed3.Timeout(trialTimeout);
    }
    if (fed3.activePoke == 0 && fed3.Right) {
      fed3.logRightPoke();
      if (random(100) < probability) {
        fed3.ConditionedStimulus(); fed3.Feed();
      } else {
        fed3.Tone(4000, 200);
      }
      counter++; fed3.Timeout(trialTimeout);
    }
  }
  // Mode 14: Bandit (probabilistic, blocks of pelletsToSwitch)
  else if (fed3.FEDmode == 14) {
    fed3.sessiontype = "Bandit";
//    fed3.countAllPokes = false;
//    fed3.LoRaTransmit = false;
    fed3.pelletsToSwitch = 20;
    fed3.prob_left  = probs[0];
    fed3.prob_right = probs[1];
    fed3.allowBlockRepeat = false;
    // Switch block?
    if (pellet_counter == fed3.pelletsToSwitch) {
      pellet_counter = 0;
      new_prob = probs[random(0, 2)];
      if (!fed3.allowBlockRepeat) {
        while (new_prob == fed3.prob_left) {
          new_prob = probs[random(0, 2)];
        }
      }
      fed3.prob_left  = new_prob;
      fed3.prob_right = 100 - fed3.prob_left;
    }
    // Left poke
    if (fed3.Left) {
      fed3.BlockPelletCount = pellet_counter;
      fed3.logLeftPoke();
      delay(1000);
      if (random(100) < fed3.prob_left) {
        fed3.ConditionedStimulus(); fed3.Feed();
        pellet_counter++;
      } else {
        fed3.Tone(300, 600);
        fed3.Timeout(timeoutIncorrect);
      }
    }
    // Right poke
    if (fed3.Right) {
      fed3.BlockPelletCount = pellet_counter;
      fed3.logRightPoke();
      delay(1000);
      if (random(100) < fed3.prob_right) {
        fed3.ConditionedStimulus(); fed3.Feed();
        pellet_counter++;
      } else {
        fed3.Tone(300, 600);
        fed3.Timeout(timeoutIncorrect);
      }
    }
  }
  // Mode 15: Deterministic Bandit (100–0 reward, switch after fixed pellets)
  else if (fed3.FEDmode == 15) {
    fed3.sessiontype = "DetBandit";
    fed3.disableSleep();
    // Switch when threshold reached
    if (pellet_counter_det == deterministicPelletsToSwitch) {
      pellet_counter_det = 0;
      rewardLeft = !rewardLeft;
    }
    // Left poke
    if (fed3.Left) {
      fed3.BlockPelletCount = pellet_counter_det;
      fed3.logLeftPoke();
      delay(1000);
      if (rewardLeft) {
        fed3.ConditionedStimulus(); fed3.Feed();
        pellet_counter_det++;
      } else {
        fed3.Tone(300, 600);
        fed3.Timeout(timeoutIncorrect);
      }
    }
    // Right poke
    if (fed3.Right) {
      fed3.BlockPelletCount = pellet_counter_det;
      fed3.logRightPoke();
      delay(1000);
      if (!rewardLeft) {
        fed3.ConditionedStimulus(); fed3.Feed();
        pellet_counter_det++;
      } else {
        fed3.Tone(300, 600);
        fed3.Timeout(timeoutIncorrect);
      }
    }
  }

  fed3.run();
}

// Helper for mode 12
void checkReset() {
  if (fed3.unixtime - poketime >= resetInterval) {
    pellets_in_current_block = 0;
    fed3.BlockPelletCount = pellets_in_current_block;
    poke_num = 0;
    pokes_required = 1;
    fed3.FR = pokes_required;
    Serial.println("\n****");
    fed3.pixelsOn(5, 5, 5, 5);
    delay(200);
    fed3.pixelsOff();
    poketime = fed3.unixtime;
  }
}

// Serial output utility for mode 12
void serialoutput() {
  Serial.print("Unixtime: "); Serial.println(fed3.unixtime);
  Serial.println("Pellets   RightPokes   LeftPokes   Poke_Num  Pel  Pokes_Required  PokeTime   Reset  FR");
  Serial.print("   "); Serial.print(fed3.PelletCount); Serial.print("          ");
  Serial.print(fed3.RightCount);   Serial.print("          ");
  Serial.print(fed3.LeftCount);    Serial.print("          ");
  Serial.print(poke_num);          Serial.print("          ");
  Serial.print(pellets_in_current_block); Serial.print("          ");
  Serial.print(pokes_required);    Serial.print("       ");
  Serial.print(poketime);          Serial.print("          ");
  Serial.print(fed3.FR);           Serial.println("\n");
}
