"""
Copyright (c) 2016 Fraunhofer FKIE

"""
import sys
from getpass import getpass


def get_credentials(domain):
    sys.stderr.write ("Authentication required for %s\n" % domain)
    while True:
        login = raw_input("Username: ")
        if login == "": continue
        passwd = getpass("Password: ")
        if passwd == "":
            sys.stderr.write("Starting over\n\n") 
            continue
        return login, passwd
