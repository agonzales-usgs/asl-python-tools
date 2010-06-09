try:
    import msvcrt
    PLAT = 'WIN'
except:
    import sys, tty, termios
    PLAT = 'POSIX'

class Getch(object):
    def __init__(self, platform):
        if platform == 'WIN':
            self.getch = self.getch_win
        else:
            self.getch = self.getch_posix
            self.fd = sys.stdin.fileno()
            self.old_settings = termios.tcgetattr(self.fd)
        self.platform = platform
    
    def getch_posix(self):
        self.old_settings = termios.tcgetattr(self.fd)
        try:
            tty.setraw(sys.stdin.fileno())
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old_settings)
        return ch

    def getch_win(self):
        return msvcrt.getch()

    def __del__(self):
        if self.platform != 'WIN':
            termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old_settings)

getch = Getch(PLAT).getch

