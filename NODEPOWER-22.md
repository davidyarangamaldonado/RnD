**Test Procedure – Line to Battery Backup \& Battery to Line Transition**



1)Conduct a visual inspection of the EUTs. Document and record any anomalies.

2)Conduct an operational check of the EUTs

&nbsp;	a)Verify all output voltages Correct

&nbsp;	b)Verify power consumption per node

3)Connect external backup batteries to AC source

4)Turn the battery switch on the AC supply to the “ON” position

5)Connect current clamp to the “Line” output of the AC source

&nbsp;	a)Set Current clamp to 100 mv/A

&nbsp;	b)Connect Current clamp output to CH3 of Oscilloscope

&nbsp;	c)Set Oscilloscope attenuation to 10x

&nbsp;	d)Set units to Current \[A] 

6)Connect AC \[CH1] / DC \[CH2] output to Oscilloscope

&nbsp;	a)DC - Set Oscilloscope probe attenuation to 10x  

&nbsp;	b)Set Channel V/div to 5v/Div (User discretion as needed)

&nbsp;	c)AC – Set Oscilloscope probe to 50x

&nbsp;	d)Set Channel to 100V/Div (User discretion as needed – Probe dependent)

7)Set Oscilloscope acquisition to “Scroll” Mode and horizontal scale to 500mS/div

8)Turn Power on AC source

9)Turn each node on 1 though 7

10)When all nodes are powered up (Green: DC Out, Green: AC IN) Switch the AC power off and capture the waveform when at the moment the AC power is    removed.  The XM supply will transition to battery back-up.

&nbsp;	a)Note if any of the Nodes Green: DC OUT or Green: AN IN LEDs turn RED	

&nbsp;		i)Document any failures

&nbsp;	b)Record the wave forms

11)Wait 5 seconds

12)Turn AC source back on

&nbsp;	a)With the Oscilloscope in roll mode capture the event when the XM transitions from battery back-up to Line power

&nbsp;	b)Note if any of the Nodes Green: DC OUT or Green: AN IN LEDs turn RED

&nbsp;		i)Document any failures

&nbsp;	c)Record the wave forms

13)Wait 5 seconds

14)Repeat steps 10 through 13 for TEN iterations.  Observer and document any failures.

15)Shut off one node

16)Repeat steps 10 through 15 until one node is left.  This will test a network configuration from all 7 nodes down to 1 node.

17)Run test on all AC power sources (XM2, XM3)





**Notes**



* Test with dual and single supply configurations. Observe if they perform similarly. 
* Do not forget to test with all configuration from 7 nodes to 1 node, with 7 nodes being the worst-case network topology. 
* If nodes are not available, use a module-level network instead. 
