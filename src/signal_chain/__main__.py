import sys

from signal_chain.app import Application

app = Application(sys.argv)
sys.exit(app.run())
