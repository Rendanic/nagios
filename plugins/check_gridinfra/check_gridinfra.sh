#!/bin/bash
#
# Version 0.1
#
# Copyright 2013 (c) Thorsten Bruhns (tbruhns@gmx.de)
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

# This plugins searchs for Resources in crs in State OFFLINE or INTERMEDIATE
# Resources with STARTMODE=never are ignored. Same applies for ora.ons and ora.gds.
# The number of voting-disks is checked. 1, 3 or 5 votedisks are expected!
# The plugin is aware of Grid Infrastructure and Oracle Restart. The check for
# votedisks are skipped in an Oracle Restart Environment!
#
# This plugin need sudo to work with nrpe
# the nrpe-owner will use the following commands with sudo:

# sudo-User         command
# CRS_OWNER         $CRS_HOME/bin/crsctl
# CRS_OWNER         $CRS_HOME/bin/orabase
# CRS_OWNER         $CRS_HOME/bin/ocrcheck
# CRS_OWNER         $CRS_HOME/bin/ocrconfig

# we do only a small check of running processes due to crsctl will
# return a hughe amount of errors when crsd isn't running
#
# example sudo-setup for nrpe:
#Defaults:nrpe    !requiretty
#Cmnd_Alias    CRSCTL =  /u01/app/11.2.0.3/grid/bin/crsctl
#Cmnd_Alias    ORABASE = /u01/app/11.2.0.3/grid/bin/orabase
#Cmnd_Alias    OCRCHECK = /u01/app/11.2.0.3/grid/bin/ocrcheck
#Cmnd_Alias    OCRCONFIG = /u01/app/11.2.0.3/grid/bin/ocrconfig
#User_Alias     NRPE_ADMIN = nagios, nrpe
#NRPE_ADMIN ALL = (oracle) NOPASSWD: CRSCTL, ORABASE, OCRCONFIG, OCRCHECK


PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin

PROGNAME=`basename $0`
PROGPATH=`echo $0 | sed -e 's,[\\/][^\\/][^\\/]*$,,'`
REVISION=$Version$


GI_Filter="((STATE = OFFLINE) OR (STATE = INTERMEDIATE)) AND (TYPE != ora.ons.type) AND (TYPE != ora.gsd.type) AND (AUTO_START != never)"

check_sudo() {
	sudo -l > /dev/null 2>&1
	retcode=${?}
	if [ ${retcode} -ne 0 ]
	then
		echo "CRITICAL - sudo not working for: sudo -l "
		exit 2
	fi
}

get_gi_type() {
	# Do we have Oracle Restart or full Grid Infrastructure?
	# Oracle Restart => OCR-Location is $ORACLE_HOME/cdata/localhost/local.ocr
	${OCRCHECKCMD} -config | grep $ORACLE_HOME/cdata/localhost/local.ocr > /dev/null
	retcode=${PIPESTATUS[1]}
	
	if [ ${retcode} -eq 0 ]
	then
		# We have Oracle Restart
		export ORACRS_TYPE=Restart

		# We don't have ons on Oracle Restart
		# => Ignore state of ora.ons.type
		GI_Filter="((STATE = OFFLINE) OR (STATE = INTERMEDIATE)) AND (TYPE != ora.ons.type) AND (TYPE != ora.gsd.type) AND (AUTO_START != never)"
	else
		# We have a full Oracle Grid Infrastructure Environment!
		export ORACRS_TYPE=GridInfra

		# Ignore state of gsd
		# GSD isn't used these days!
		GI_Filter="((STATE = OFFLINE) OR (STATE = INTERMEDIATE)) AND (TYPE != ora.gsd.type) AND (AUTO_START != never)"
	fi 
}

check_votedisks() {
	# Check for votedisks only needed on real Grid-Infrastructure!
	if [ ${ORACRS_TYPE} = 'GridInfra' ]
	then
		# we are on a real Grid-Infrastructure
		# We need 1,3 or 5 voting discs
		# Cluster won't work if we have less then number of votedisks / 2
		# A cluster with 3 needed disks won't work with 1. the same aplies for 5.
		# => Easy check possible, because 2 or 4 ONLINE-Votedisks is an error!
		votecount=`${CRSCTLCMD} query css votedisk| cut -b5- | grep ^ONLINE | wc -l`
		if [ ${votecount:-0} -eq 1 -o ${votecount:-0} -eq 3 -o ${votecount:-0} -eq 5 ]
		then
			# Votecount is ok
			# => we can step to Resourcecheck of the cluster!
			votedisksok=yes
		else
			echo "CRITICAL - Number of Votingdisks not ok. check votedisks with 'crsctl query css votedisk' Count "${votecount:-1}
			exit 2
		fi


	fi
}

get_CRSOWNER() {
	# who is clusterwareowner?
	# User of running ASM-Instance is clusterware-Owner!
	ORACRSOWNER=`ps -elf | grep asm_pmon_+ASM | grep -v " grep asm_pmon_+ASM" | cut -d" " -f3`
	retcode=${PIPESTATUS[1]}
	if [ ${ORACRSOWNER:-leer} = 'leer' ]
	then
		# We can't get the owner of ASM. mostly this is due to a down ASM-Instance
		# Cluster won't work without ASM!
		echo "CRITICAL - ASM is down or unknown CRSOWNER is unknown,"
		exit 2
	else
		export ORACRSOWNER
	fi

}

set_env()
{
	check_sudo

	ORATAB=/etc/oratab

	# set environment from /etc/oratab
	# 1st line with +ASM will be used for CRS_HOME
	ORACLE_SID=`grep "^+ASM" ${ORATAB} |cut -d":" -f1`
	if [ ${?} -ne 0 ]
	then
		echo "CRITICAL - ASM-Environment can't be found in oratab!"
		exit 2
	else
		export ORACLE_SID

		# getting ORACLE_HOME from oratab
		ORACLE_HOME=`cat ${ORATAB} | grep "^"${ORACLE_SID} | cut -d":" -f2`
		export ORACLE_HOME
		
		get_CRSOWNER

		# if we have a grid infrastructure or oracle restart we get the ORACLE_BASE with
		# a executable from Oracle!
		ORACLE_BASE=`sudo -n -u ${ORACRSOWNER} ${ORACLE_HOME}/bin/orabase`
		export ORACLE_BASE

		PATH=${PATH}:${ORACLE_HOME}/bin
		export PATH
	fi

	CRSCTLCMD=$ORACLE_HOME/bin/crsctl
	CRSCTLCMD="sudo -n -u "${ORACRSOWNER}" "${CRSCTLCMD}
	OCRCHECKCMD="sudo -n -u "${ORACRSOWNER}" "$ORACLE_HOME/bin/ocrcheck


}

print_usage() {
	echo "Usage: $PROGNAME"
}

print_help() {
	echo ""
	print_usage
	echo ""
	echo "This plugin checks a running Oracle Grid-Infrastructure for OFFLINE und INTERMEDIATE-Resources."
	echo ""
	exit 0
}


check_grid_infra() {
	execcmd="$CRSCTLCMD stat res -t -w "
	count=$($execcmd "${GI_Filter}" | wc -l)
	# retcode and cound=0 => all is ok!
	retcode=${PIPESTATUS[0]}
	if [ ${retcode:-1} -ne 0 ]
	then
		echo "Error while executing crsctl. Returencode="${retcode}
	else
		if [ ${count:-1} -eq 0 ]
		then
			# all resources are fine!
			echo "OK - All Resources are ONLINE!"
			exit 0
		else
			execcmd="$CRSCTLCMD stat res  -w "
			result=$($execcmd "${GI_Filter}" | egrep "^NAME=|^LAST_SERVER=|^STATE="| cut -d"=" -f2- )
			echo "CRITICAL - Problems with some Resources! Check with 'crsctl stat res -t'. Details: "$result
			exit 2
		fi
	fi

}


set_env $*


case "$1" in
	--help)
		print_help
		exit 0
		;;
	-h)
		print_help
		exit 0
		;;
	*)
		get_gi_type
		check_votedisks
		check_grid_infra
		;;
esac
