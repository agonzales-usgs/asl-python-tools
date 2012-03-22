import math
from jtk import Pretty

class Calib:
    def __init__(self, responses, station=None, channel=None):
        self.responses = responses
        if station:
            st_info = responses.dataless.map['stations'][station]
        else:
            st_info = sorted(responses.dataless.map['stations'].items())[0][1]

        if channel:
            ch_info = st_info['channels'][channel]
        else:
            ch_info = sorted(st_info['channels'].items())[0][1]

        #print "epochs:", sorted(ch_info['epochs'].keys())
        #print "selected epoch:", sorted(ch_info['epochs'].items(), reverse=True)[0][0]
        self.map = sorted(ch_info['epochs'].items(), reverse=True)[0][1]

        self.calper = None
        self.calib = None

  # returns tuple of (CALPER,CALIB)
    def calculate_calib(self, calper, correct_calib=False):
        self.calper = calper

      # evaluate at this frequency
        frequency = 1.0/calper

        stage_map = self.map

      # B053F04 (mid-band gain of the instrument)
        mbs_gain = float(stage_map['stages'][1][58].get_values(4)[0][0])

      # B058F04 (digitizer_gain = 2**24 Counts / 40 Volts)
        digitizer_gain = float(stage_map['stages'][2][58].get_values(4)[0][0])

      # B053F07 (A0 normalization factor)
        a0 = float(stage_map['stages'][1][53].get_values(7)[0][0])

      # B053F09 (num zeros)
        num_zeros = float(stage_map['stages'][1][53].get_values(9)[0][0])
        zero_parts = stage_map['stages'][1][53].get_values(10,11)
        zeros = zip(*zero_parts)

      # B053F14 (num poles)
        num_poles = float(stage_map['stages'][1][53].get_values(14)[0][0])
        pole_parts = stage_map['stages'][1][53].get_values(15,16)
        poles = zip(*pole_parts)

        amplitude = 1.0
        if correct_calib:
            c_numerator = complex(a0, 0.0) # represents a complex number
            for zero in zeros:
                # Zr (real from this zero in RESP)
                # Zi (imaginary from this zero in RESP)
                Zr,Zi = map(float, zero)
                #print "Zr =", Zr
                #print "Zi =", Zi
                c_numerator *= complex(0.0, 2*math.pi*frequency) - complex(Zr, Zi)

            c_denominator = complex(1, 0.0)
            for pole in poles:
                # Zr (real from this pole in RESP)
                # Zi (imaginary from this pole in RESP)
                Pr,Pi = map(float, pole)
                #print "Pr =", Pr
                #print "Pi =", Pi
                c_denominator *= complex(0.0, 2*math.pi*frequency) - complex(Pr, Pi)

            c_tf = c_numerator / c_denominator

            # calculate the amplitude response at the given period
            amplitude = math.sqrt(c_tf.real**2 + c_tf.imag**2) # back to a real number
            #print "amplitude =", amplitude

        
        period_gain = amplitude * mbs_gain # volts/(meter/second) [gain with reference to the selected period]

        sensor_gain = period_gain * (2*math.pi*frequency) # volts/meter
        
        calib_meters = 1.0 / (sensor_gain * digitizer_gain)
        self.calib = calib_meters * (10 ** 9) # nanometers/counts

        #print "period_gain:", period_gain 
        #print "digitizer_gain:", digitizer_gain 

        return (self.calper, self.calib)

