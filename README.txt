CIF model of a typical roadside unit (RSU), used for synthesis and implementation.

File structure:
- Folder generated_files initially contains the models that were produced by the configurator. All 
  models created by tools are added to the folder.
- Folder simulation contains all additional files needed for simulation of the generated controller.
- Folder CCcom contains files needed for simulation of the central control. Note that generated file
  constants.cif is also required. This folder also contains the java code for the communication that
  is used in both RSU and CC simulations.
- Folder tools contains all Tooldef scripts that can be used to automatically run the synthesis, 
  simulation and code generation.

Hardware file:
  To allow both simulation and implementation of the PLC code, one adjustment needs to be made in
  generated_files/hardware.cif. When using simulation, plant SendTrigger should always allow event
  e_sent. To do this, the unguarded event (line 21) should be uncommented, and the guarded event 
  (line 22) should be commented. For implementing the PLC code, the e_sent event should only be 
  allowed when it is possible to send a new message, so the guarded event (line 22) should be used.

To synthesize a supervisor:
  - run tool1_synthesis.tooldef2.
  - in the options pop-up, click OK.
  This generates a supervisor (generated_files/G_supervisor.cif) and controller 
  (generated_files/G_controller.cif). Note that controller checks are not applied.

To start the simulation of the CC:
  - set the IP-address HOSTADDR in CCcom/CCcom.py. For simulation, 127.0.0.1 is recommended. For 
    HIL, the network address should be used.
  - set the IP-address RSUADDR in CCcom/CCcom.py as the IP-address of the RSU.
  - run CCcom/CCcom.py (in python).
  - run tool_CC_simulation.tooldef2.
  - in the options pop-up, click OK.
  This creates an ethernet connection for the simulated CC. Next, the simulation itself is started.
  At regular intervals, the CC will request messages from the connection, and receive one, if 
  messages are present.
  
To start the simulation of the RSU:
  - ensure hardware.cif is correct.
  - set the IP-address HOSTADDR in Simulation/RSUcom.py. For simulations on one PC, 127.0.0.1 is 
    recommended. Otherwise, the network address should be used.
  - set the IP-address CCADDR in Simulation/RSUcom.py as the address of the CC. For the simulation
    CC, this should match the HOSTADDR in CCcom/CCcom.py.
  - run Simulation/RSUcom.py (in python).
  - run tool2_simulation.tooldef2.
  - in the options pop-up, click OK.
  This creates an ethernet connection for the simulated RSU. Next, the simulation itself is started.
  At regular intervals, the RSU will request messages from the connection, and receive one, if 
  messages are present.

To generate PLC code for the RSU:
  - ensure hardware.cif is correct.
  - run tool3_code_generation.tooldef2.
  - in the options pop-up under Generator > PLC code target type, select the desired target type.
  - click OK.
  The PLC code will be added to generated_files/PLC_code/ if multiple files are created. Otherwise a
  file generated_files/PLC_code is created with the generated code.
