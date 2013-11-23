#!/usr/bin/python
"""

 (c) 2013  Thorsten Bruhns (thorsten.bruhns@opitz-consulting.com)

The Oracle-Environemnt must be set before executing this script.
cx_Oracle needs LD_LIBRARBY_PATH and ORACLE_HOME before starting this script.

There are working RPMs for Python on Sourceforge.

=> cx_Oracle is required! (http://cx-oracle.sourceforge.net/)
=> ORACLE_HOME and LD_LIBRARY_PATH must be set

IMPORTANT!
cx_Oracle has a restriction when connecting with ' as sysdba' or ' as sysoper'. 'as sysasm' or
'as syssnmp' is not suppoted!
Sulution:
Create a new user with 'as sysdba' priviledges.
create user dbsnmp identified by dbsnmp;
grant sysdba to dbsnmp;

=> This plugin is working with ' as sysdba'
"""
import sys, getopt, traceback

try:
    import cx_Oracle
except ImportError, e:
    print "CRITICAL - Python is unable to import cx_Oracle. Please install cx_Oracle from http://cx-oracle.sourceforge.net"
    sys.exit(2)


class nagios():
    """
Copyright (c) 2013 Thorsten Bruhns <thorsten.bruhns@opitz-consulting.com>

Version 0.1

This plugin Checks Diskgroups from Oracle Automatic Storage Management.
Offline Disks in a Diskgroup results in a CRITCAL.
Warning and Critical values are for Diskgroup-usage.

The login user need 'sysdba' rights in ASM. This is due to a restriction in cx_Oracle.


Usage:
  check_oracle_asmdg.py -w <warning in pct> -c <critical in pct> -d <dgname>
[-u <username>] [-p <password>] [-s <ASM-Servicename>]

Options:
 -h, --help
    Print detailed help screen
 -V, --version
 -w, --warning PERCENT
    Exit with WARNING status if usage is more than PERCENT
 -c, --criticalPERCENT
    Exit with CRITICAL status if usage is more than PERCENT
 -u, --username STRING
    The username for login to ASM
    Default: dbsnmp
 -p, --password STRING
    The password for login to ASM
    Default: dbsnmp
 -d, --diskgroup STRING
    Diskgroup-Name
 -s, --service STRING
    Service-Name for connect to ASM
    Default: ASM

    """
    def __init__(self, argv):
        self.nagiosretcode = -1
        self.nagiosretstring = ''
        self.argdictionary = {}
        self.argdictionary['warning'] = 70
        self.argdictionary['critical'] = 90
        self.argdictionary['port'] = 1521
        self.argdictionary['hostname'] = 'localhost'
        self.argdictionary['username'] = 'dbsnmp'
        self.argdictionary['password'] = 'dbsnmp'
        self.argdictionary['dgname'] = '<null>'
        self.argdictionary['requiredmirfree'] = False
        self.argdictionary['asmservice'] = '+ASM'

        self.getparameter(argv)
        self.checkParameter()


    def setNagiosRetcode(self, newState):
        """
        State is checked against the actual Retval and incremented up to 2 for CRITICAL!
        Returncode of this procedure:
        0 => OK
        1 => WARNING
        2 => CRITICAL
        -1 => UNKNOWN State!
        """
        if self.nagiosretcode < newState:
            self.nagiosretcode = newState

    def getASMdata(self):
        dbasm = oraASM(self.argdictionary['username'], self.argdictionary['password'], self.argdictionary['asmservice'])
        dbasm.getASMdgdata(self.argdictionary['dgname'])

        return dbasm

    def checkOfflineDIsks(self,dbasm):
        """
        Check Offline Disks
        """
        OfflineDisks = dbasm.checkOfflineDisk()
        if OfflineDisks > 0:
            self.nagiosretstring = self.nagiosretstring + ' ' + str(OfflineDisks) + ' Offline Disks in Diskgroup ' \
                                    + self.argdictionary['dgname'] + ' '
            self.setNagiosRetcode(2)
        else:
            self.setNagiosRetcode(0)

    def checkDiskgroupUsage(self, dbasm):
        UsedSpace = dbasm.getUsedSpacePct()

        if UsedSpace > int(self.argdictionary['critical']):
            self.setNagiosRetcode(2)
        else:
            if UsedSpace > int(self.argdictionary['warning']):
                self.setNagiosRetcode(1)
        self.nagiosretstring += "Diskgroup used " + str(round(UsedSpace, 2)) + "% (" \
                                + str(dbasm.DGinfo['REAL_USED_MB']) + '/' + str(dbasm.DGinfo['REAL_TOTAL_MB']) + ')'


    def printnagiosresult(self):
        """
        this function prints the resultstring for nrpe. It exits the script with the required exitcode!
        """
        if self.nagiosretcode == 0:
            self.nagiosretstring = 'OK - ' + self.nagiosretstring
        elif self.nagiosretcode == 1:
            self.nagiosretstring = 'WARNING - ' + self.nagiosretstring
        elif self.nagiosretcode == 2:
            self.nagiosretstring = 'CRITICAL - ' + self.nagiosretstring
        else:
            self.nagiosretstring = 'UNKNOWN - unknown returncode in plugin ' + \
                                   self.nagiosretcode + " " + self.nagiosretstring
        print self.nagiosretstring
        sys.exit(self.nagiosretcode)

    def doAll(self):

        dbasm = self.getASMdata()
        if 'NAME' not in dbasm.DGinfo:
            # we have no data from ASM
            self.setNagiosRetcode(2)
            self.nagiosretstring = "No Data for Diskgroup " + str(self.argdictionary['dgname']) + " "
        else:
            self.checkOfflineDIsks(dbasm)
            self.checkDiskgroupUsage(dbasm)

        self.printnagiosresult()

    def checkParameter(self):
        """
        Validating the given parameters
        """

        if int(self.argdictionary['warning']) > int(self.argdictionary['critical']):
            print "Invalid values. warning (" + self.argdictionary['warning'] + ")" \
                  " > critical(" + self.argdictionary['critical'] + ")"
            sys.exit(2)

        if int(self.argdictionary['warning']) > 100 or int(self.argdictionary['critical']) > 100:
            print "Invalid values. warning (" + self.argdictionary['warning'] + ") > 100 " \
                  " or critical(" + self.argdictionary['critical'] + ") > 100"
            sys.exit(2)
        if self.argdictionary['dgname'] == '<null>':
            print "missing parameter for diskgroup"
            sys.exit(2)


    def getparameter(self, argv):

        scriptname = argv[0]
        arglist = argv[1:]
        helpline = scriptname + ' -w <warning in pct> -c <critical in pct> -u <username> ' \
                                '-p <password> -d <dgname> -s <ASM-Servicename>'

        try:
            opts, args = getopt.getopt(arglist,"?hrw:c:u:p:P:H:d:s:",["help", "service", "requiredmirfree"])
        except getopt.GetoptError:
            print helpline
            sys.exit(2)

        for opt, arg in opts:
            if opt in ("-?", "-h"):
                print helpline
                sys.exit()
            elif opt in ("--help"):
                print nagios.__doc__
                sys.exit()
            elif opt in ("-w", "--warning"):
                self.argdictionary['warning'] = arg
            elif opt in ("-c", "--critical"):
                self.argdictionary['critical'] = arg
            elif opt in ("-u", "--username"):
                self.argdictionary['username'] = arg
            elif opt in ("-p", "--password"):
                self.argdictionary['password'] = arg
            elif opt in ("-P", "--port"):
                self.argdictionary['port'] = arg
            elif opt in ("-H", "--hostname"):
                self.argdictionary['hostname'] = arg
            elif opt in ("-d", "--dgname"):
                self.argdictionary['dgname'] = arg
            elif opt in ("-s", "--service"):
                self.argdictionary['asmservice'] = arg
            elif opt in ("-r", "--requiredmirfree"):
                self.argdictionary['requiredmirfree'] = True


class oraASM():
    def __init__(self, username, password, asmservice):
        try:
            self.db = cx_Oracle.connect(username, password, 'localhost:1521/' + asmservice, mode = cx_Oracle.SYSDBA)
            self.DGinfo = {}
        except cx_Oracle.DatabaseError:
            type_, value_, traceback_ = sys.exc_info()
            ex = traceback.format_exception(type_, value_, traceback_)
            print ex[-1].strip('\n')
            sys.exit(2)


    def getASMdgdata(self, dgname):
        # self.ASMdgdata = []
        cursor = self.db.cursor()
        cursor.execute('select NAME, STATE, TYPE, OFFLINE_DISKS' +
                       ', TOTAL_MB, FREE_MB, REQUIRED_MIRROR_FREE_MB ' +
                       'from v$asm_diskgroup '
                       'where name = \'' + dgname + '\'')
        self.__ASMdgdata = cursor.fetchall()

        if self.__ASMdgdata != []:
            self.DGinfo['NAME'] = self.__ASMdgdata[0][0]
            self.DGinfo['STATE'] = self.__ASMdgdata[0][1]
            self.DGinfo['TYPE'] = self.__ASMdgdata[0][2]
            self.DGinfo['OFFLINE_DISKS'] = self.__ASMdgdata[0][3]
            self.DGinfo['TOTAL_MB'] = self.__ASMdgdata[0][4]
            self.DGinfo['FREE_MB'] = self.__ASMdgdata[0][5]
            self.DGinfo['REQUIRED_MIRROR_FREE_MB'] = self.__ASMdgdata[0][6]

            # we calculate the detail information and put them into the dictionary DGinfo
            if self.DGinfo['TYPE'] == 'EXTERN':
                self.DGinfo['REAL_FREE_MB'] = self.DGinfo['FREE_MB']
                self.DGinfo['REAL_TOTAL_MB'] = self.DGinfo['TOTAL_MB']
                self.DGinfo['REAL_TOTAL_MB'] = self.DGinfo['TOTAL_MB']
                self.DGinfo['REAL_USED_MB'] = int(self.DGinfo['TOTAL_MB']) - int(self.DGinfo['FREE_MB'])
                self.DGinfo['REAL_USABLE_MB'] = self.DGinfo['REAL_USED_MB']
            if self.DGinfo['TYPE'] == 'NORMAL':
                self.DGinfo['REAL_FREE_MB'] = int(self.DGinfo['FREE_MB'])/2
                self.DGinfo['REAL_TOTAL_MB'] = int(self.DGinfo['TOTAL_MB'])/2
                self.DGinfo['REAL_USED_MB'] = int(self.DGinfo['TOTAL_MB'])/2 - int(self.DGinfo['FREE_MB'])/2
                self.DGinfo['REAL_USABLE_MB'] = (int(self.DGinfo['TOTAL_MB']) - \
                                                 int(self.DGinfo['REQUIRED_MIRROR_FREE_MB']))/2 - int(self.DGinfo['FREE_MB'])/2
            if self.DGinfo['TYPE'] == 'HIGH':
                self.DGinfo['REAL_FREE_MB'] = int(self.DGinfo['FREE_MB'])/3
                self.DGinfo['REAL_TOTAL_MB'] = int(self.DGinfo['TOTAL_MB'])/3
                self.DGinfo['REAL_TOTAL_MB'] = int(self.DGinfo['TOTAL_MB'])/3
                self.DGinfo['REAL_USABLE_MB'] = (int(self.DGinfo['TOTAL_MB']) - \
                                                 int(self.DGinfo['REQUIRED_MIRROR_FREE_MB']))/3 - int(self.DGinfo['FREE_MB'])/3

            if self.DGinfo['REAL_USABLE_MB'] < 0:
                self.DGinfo['REAL_USABLE_MB'] = 0

    #        self.DGinfo['TOTAL_MB'] = self.__ASMdgdata[0][0]
        cursor.close()


    def checkOfflineDisk(self):
        """
        This procedure checks for offline disks in self.ASMdgdata
        """
        offlinedisks = self.DGinfo['OFFLINE_DISKS']
        return offlinedisks


    def getUsedSpacePct(self):
        """
        
        """
        UsedPct = -1

        UsedPct = 100 - (int(self.DGinfo['FREE_MB']) / float(self.DGinfo['TOTAL_MB'])) * 100
#        UsedPct = 100 - (freel_mb / float(total_mb)) * 100
        return UsedPct


    def printdata(self):
        for item in self.ASMdgdata:
            print item


nagplugin = nagios(sys.argv[0:])
nagplugin.doAll()
