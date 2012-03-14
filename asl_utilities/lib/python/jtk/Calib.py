import math

class Calib:
    def __init__(self, responses, correct_calib=False):
        self.responses = responses
        self.resp_map = responses.resp_map
        self.results = None
        self.correct_calib = correct_calib

  # returns tuple of (CALPER,CALIB)
    def calculate_calib(self, calper):

      # evaluate at this frequency
        frequency = 1.0/calper

      # B053F04 (mid-band gain of the instrument)
        mbs_gain = float(self.resp_map[53][4]['value'])

      # B058F04 (digitizer_gain = 2**24 Counts / 40 Volts)
        digitizer_gain = float(self.resp_map[58][4]['value'])

      # B053F07 (A0 normalization factor)
        a0 = float(self.resp_map[53][7]['value'])

      # B053F09 (num zeros)
        num_zeros = int(self.resp_map[53][9]['value'])
        zeros_map = self.resp_map[53][9]['children']
        zeros_parts = []
        # B053F10-13 (zero values)
        for field_id in sorted(zeros_map.keys()):
            zeros_parts.append(zeros_map[field_id]['value'])
        zeros = zip(*zeros_parts)

      # B053F14 (num poles)
        num_poles = int(self.resp_map[53][14]['value'])
        poles_map = self.resp_map[53][14]['children']
        poles_parts = []
        # B053F15-18 (pole values)
        for field_id in sorted(poles_map.keys()):
            poles_parts.append(poles_map[field_id]['value'])
        poles = zip(*poles_parts)

        amplitude = 1.0
        if self.correct_calib:
            c_numerator = complex(a0, 0.0) # represents a complex number
            for zero in zeros:
                # Zr (real from this zero in RESP)
                # Zi (imaginary from this zero in RESP)
                Zr,Zi,_,_ = map(float, zero)
                c_numerator *= complex(0.0, 2*math.pi*frequency) - complex(Zr, Zi)

            c_denominator = complex(1, 0.0)
            for pole in poles:
                # Zr (real from this pole in RESP)
                # Zi (imaginary from this pole in RESP)
                Pr,Pi,_,_ = map(float, pole)
                c_denominator *= complex(0.0, 2*math.pi*frequency) - complex(Pr, Pi)

            c_tf = c_numerator / c_denominator

            # calculate the amplitude response at the given period
            amplitude = math.sqrt(c_tf.real**2 + c_tf.imag**2) # back to a real number

        
        period_gain = amplitude * mbs_gain # volts/(meter/second) [gain with reference to the selected period]

        sensor_gain = period_gain / (2*math.pi*frequency) # volts/meter
        
        calib_meters = 1.0 / (sensor_gain * digitizer_gain)
        self.results = (calper,calib_meters * (10 ** 9)) # nanometers/counts
