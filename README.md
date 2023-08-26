# oci-infra-mgr
The scripted starting and stopping of OCI objects. 

## Introduction
The purpose of this project is to demonstrate how the OCI SDK can be used to automatically shutdown and startup OCI objects (e.g. compute instances, MySQL HeatWave instances, etc.). The reason for wanting to shutdown objects is to save money: in OCI you are only charged for the resource you use. For example a compute instance (Virtual Machine) is typically comprised of the following chargeable components: OCPUs (cores), memory and storage. If a compute instance is shutdown its cores and memory are freed and no charge is levied. Note that storage will still be charged, because the compute instance's OS and user files remain in place. However, the bulk of the cost is in cores and memory, therefore if a non-critical compute instance can be shutdown for even a small period of time considerable savings can be made.

Please note: if you choose to use the software that this site provides you do so entirely at your own risk. There are no guarantees or warantees associated with this software. It is your responsibility to test and prove that it is fit for your purposes.

## High-Level Requirements
It is envisaged that this project will typically be used with OCI objects that have non-critical roles, for example compute instances in non-production environments, and that the tenancy owners will want to schedule their shutdown and startup to coincide with office hours. Therefore the primary requirement for this project can be described as the scheduled shutdown and startup of multiple OCI objects across multiple environments.

It is very likely there will be exceptional circumstances where an OCI object will either need to remain in either a running or shutdown state. 

A method of describing the OCI objects to be started and shutdown which should be flexible enough to allow the exclusion of objects that need to either remain running or shutdown.

The project's script must authenticate with the OCI tenancy and must be authorized to make changes to the OCI objects it wants to stop and start.

The projects script must provide a log of its actions so that its owners can be assured it is functioning correctly and to otherwise assist in any post-mortem activities.

The project will also need to consider testing, packaging/deployment and how the script may be extended.

## Response to High Level Requirements
Use of Python OCI SDK to script the startup and shutdown of objects. The SDK provides a full API that will allow the startup and shutdown of OCI objects. Python comes with many libraries that will facilitate the creation of the scripted solution, for example: logging, parsing of JSON files, command line options, etc. Python also has utilities that can package the scripting atefacts into a single file which simplifies deployment. Both the API and Python support the extendability of the script. 

The OCI SDK uses the OCI CLI configuration file to both provide authentication with a customer's OCI tenancy and to secure communications between the end points (i.e. from where the script is run to the OCI tenancy).

A small compute instance (possibly from the OCI free tier) will be used to host and run the script. The operating system will be Oracle Linux 8 which includes cron, an OS scheduling utility that invokes scripts and programs to run at particular times. Note that Python does not preclude the use of other operating systems. Indeed almost any mainstream operating system could be used which supports Python so long as it has a similar scheduling facility to cron.  

A JSON schema will be developed that will allow the user to precisely detail the OCI objects that will be started and shutdown. The schema will make provision for identifying exceptional cases where a scheduled run should not invoke either a start-up or shutdown.  

## Describing the infrastructure to be started and stopped: infra.json

OCI objects are logically separated into compartments. Compartments may be used to separate user sandboxes, whole environments, or work-specific areas such as networks. Compartments and OCI objects can all be identified by a unique identifier called and OCID. An OCID is a long string of nonsensical characters. Machines have no problem using OCIDs to identify objects but humans find it very difficult. Consequently, humans prefer user-friendly names. The problem with names is OCI allows duplicate names to be used. Therefore, to allow correct identification of an OCI Object by both humans and machines a combination of compartment name, compartment OCID, object name and object OCID is required. 

From a scripting perspective the object's type (e.g. compute instance, MySQL HeatWave database service) will also need to be specified. This is because an object of one type might need to started or stopped in a slightly different manner to an object of another type (these differences are reflected in the OCI SDK's API). Finally, in order to be able to exclude an object from a specific action (i.e. start and stop), an exclude flag is needed (i.e. if set to true then the object won't be stopped or started).

Given the above and the requirement to implement the description in JSON, the following JSON schema has been developed:

```json
{
    "compartments": {
        "type": "array",
        "items": {
            "name": {"type": "string"},
            "ocid": {"type": "string"},
            "objects": {
                "type", "array",
                "items": {
                    "type": {"type": "string"},
                    "name": {"type": "string"},
                    "ocid": {"type": "string"},
                    "exclude": {"type": "boolean"}
                }
            }
        }
    }
}
```
Sometimes schemas can be a little difficult to understand and so here is an implementation example 
```json
{
    "compartments": [{
        "name": "david_sandbox",
        "ocid": "ocid1.compartment.oc1..aaaaaaaaqpe**********3ya",
        "objects": [{
            "type": "compute_instance",
            "name": "app1",
            "ocid": "ocid1.instance.oc1.uk-london-1.anw**********zpq",
            "exclude": false
        },{
            "type": "compute_instance",
            "name": "app2",
            "ocid": "ocid1.instance.oc1.uk-london-1.anw**********aaq",
            "exclude": true
        },{
            "type": "mysql_database",
            "name": "db1",
            "ocid": "ocid1.mysqldbsystem.oc1.uk-london-1.aaaaaaaafbw**********d7q",
            "exclude": false
        }]
    },{
        "name": "project_XYZ_dev_env",
        "ocid": "ocid1.compartment.oc1..aaaaaaaap7**********geq",
        "objects": [{
            "type": "mysql_database",
            "name": "db1",
            "ocid": "ocid1.mysqldbsystem.oc1.uk-london-1.aaaaaaaaokg**********63q",
            "exclude": false
        },{
            "type": "compute_instance",
            "name": "app1",
            "ocid": "ocid1.instance.oc1.uk-london-1.anw**********3gq",
            "exclude": false
        }]
    }]
}
```
Some points to note:
* The JSON describes two compartments: `david_sandbox` and `project_XYZ_dev_env`.
* The first compartment details three objects which are candidates for starting and stopping, whereas the second compartment only has two objects. It is not necessary to specify every object in each compartment; only specify the objects you want.
* Note that for the objects there is duplication of names but not OCIDs. OCIDs are always unique.
* The compute instance object app2 has its `exclude` key set to `true`. This means no action (i.e. stop or start) will be performed on this object when the script runs.
* OCID strings have been obfuscated and reduced in length for the purpose of illustrations

## Script Walkthrough
The script comprises two source code files, `infraMgr.py` and `infraArgs.py`:
* `infraMgr.py` provides the logic to perform the starting/stopping of OCI objects.
* `infraArgs.py` provides two classes that are used in the handling of command line arguments: `InfraArgs` and `InfraArgsError`

At the top of the infraMgr.py script is a set of imports:
* `json` is required to provide the functionality to load and parse the infrastructure description file, infra.json (described above)
* `getopt` works with the `InfraArgs` classes to provide command line handling
* `logger` provides logging functionality
* `sys` provides an interface to the OS
* `oci` provides the implementation of the OCI API

The Python OCI APIs that are used within the script can be found by following these links:

* [oci.core.ComputeClient](https://docs.oracle.com/en-us/iaas/tools/python/2.110.2/api/core/client/oci.core.ComputeClient.html)  
* [oci.core.models.Instance](https://docs.oracle.com/en-us/iaas/tools/python/2.110.2/api/core/models/oci.core.models.Instance.html#oci.core.models.Instance) 
* [oci.mysql.DbSystemClient](https://docs.oracle.com/en-us/iaas/tools/python/2.110.2/api/mysql/client/oci.mysql.DbSystemClient.html#oci.mysql.DbSystemClient) 
* [oci.mysql.models.DbSystem](https://docs.oracle.com/en-us/iaas/tools/python/2.110.2/api/mysql/models/oci.mysql.models.DbSystem.html#oci.mysql.models.DbSystem) 
* [oci.mysql.models.StopDbSystemDetails](https://docs.oracle.com/en-us/iaas/tools/python/2.110.2/api/mysql/models/oci.mysql.models.StopDbSystemDetails.html#oci.mysql.models.StopDbSystemDetails) 

The full API can be found [here](https://docs.oracle.com/en-us/iaas/tools/python/2.110.2/api/landing.html)

The flow of the `infraMgr.py` script is very simple. The entry point can be found at the very end of the script which begins with an `if` statement that checks for the presence of a function called `main` and then calls that function passing the entire command line.

The `main` function's code is encapsulated in a `try-except` block. If an exception occurs in the logic of the `try` part then control jumps to the `except` part. The `except` part will either print a message detailing the exception to `stderr` and then exit, or write the same message to its log and then exit. The choice of action depends on whether the exception occurs before or after logging has been configured (if logging has not been configured then the message will be printed to `stderr`).

The `try` block begins by parsing the command line. If a `-h` or `--help` flag was provided on the command line then the script will call its `usage()` function. This will print to screen details of how to use the script. This will also be the case if the script is invoked without any arguments because this is the script's default action (see `infraArgs.py`). If a `-a` or `--action` flag together with an argument of either `START` or `STOP` was provided on the command line together with zero or more of the optional flags and their arguments then the `main` function will: 

* Configure logging so that all events after its configuration can be recorded in the script's log.
* Read and parse the infrastructure file (e.g. `infra.json`) into a variable such that the script can later iterate through all the objects to be actioned (i.e. either started or stopped depending upon the action argument passed in from the command line).
* Read and parse the OCI config file into a variable such that the script can later setup secure communications between its host and the user's OCI tenancy.

On completion of the above three tasks the main function will process the OCI objects. It does this by calling the script's `process_infrastructure()` function. This function takes three parameters: the variable holding the infastructure details, the action (START or STOP) to be applied to the infrastructure details, and the variable holding the OCI configuration details (to allow secure communications).

The `process_infrastructure()` function implements a nested loop: the outer loop iterates through the compartments and the inner loop iterates through each compartment's objects. If an object has its `exclude` key set to `true` then all that happens is a log entry detailing that the object will not be actioned. Otherwise, the type of the object is interrogated. If the object is of a COMPUTE_INSTANCE type then a call will be made to the `switch_compute()` function, whereas if the object is of a `MYSQL_DATABASE` type a call will be made to the `switch_mysql()` function. The `switch_compute()` and `switch_mysql()` functions take the same parameters: the variable holding the OCI configuration, the object to be actioned OCID, the name of the compartment the object belongs to, and the action to be performed on the object. The two functions perform the same task, either starting or stopping an object, but because they are of different types they use different states to describe being started or stopped, and in the case of `switch_mysql()` it is necessary to create an object that describes how a MySQL instance should be taken down. The flow of both functions can be described as follows:

* Get a client object from the tenancy
    * Client objects provide a handle to get instances of the same type and modify the same. Conceptually they act a little like a manager but given they are on the client side of the tenancy's REST server they are referred to as a client. 
* From the client object get a representation of the instance of the object
    * The instance is wrapped in a `Response` object and is accessible through the `Response` object's `data` property.
* If the passed in action is `START` and the instance is in an appropriate state (i.e. `STOPPED` for a compute instance, `INACTIVE` for a MySQL instance) then call the client's start method. Write an `INFO` entry in the log. 
    * If the instance is not in an appropriate state then write a `WARNING` entry in the log.
* If the passed in action is `STOP` and the instance is in an appropriate state (i.e. `STARTED` for a compute instance, `ACTIVE` for a MySQL instance) then call the client's stop method. Write an `INFO` entry in the log. 
    * Note that the client's stop method for a MySQL Database also requires a `oci.mysql.models.StopDbSystemDetails` parameter which details how the stop should be executed (i.e. `IMMEDIATE`, `FAST` or `SLOW`)
    * If the instance is not in an appropriate state then write a `WARNING` entry in the log.

Once `process_infrastructure()` has iterated through all the objects (calling the switch functions as appropriate) control returns to `main()`. All that `main()` has left to do is log that the run has completed and then exit. 

## Script Usage

There are two modes of usage: seeking help and performing an action. When performing an action you must specify the action and optionally provide further flags and arguments as shown.

`infraMgr.py -h`

`infraMgr.py -a <action> [-i <infrastructure-file> -l <logfile> -v <log-level> -o <oci-config-file>]`

### Modal Flags and Arguments

`-h | --help`

Displays this page. If help is requested then this page will be displayed regardless of any other actions being requested or flags used.

`-a | --action <START|STOP>`

The argument to the action flag must be either START or STOP.

### Optional Flags and Arguments

The following flags only have relevance if the action flag is used.

`-i | --infra-file <infrastructure-file>`

Where infrastructure-file includes both the path and name of the file. For example, /root/infra.json where infra.json is the file name. If this option is not used then the program will look for a file called, infra.json, in the current working directory. This file must be readable by the script.

`-o | --oci-cfg <oci-config-file>`

Where oci-config-file includes both the path and name of the file. For example, /root/config where config is the file name. If this option is not used then the program will attempt to read this file in the default location for the underlying OS, e.g. for the root user on Oracle Linux this will be /root/.oci/config. This file must be readable by the script.

`-l | --logfile <logfile>`

For example the path could be /root/infra.log where infra.log is the file name. If this option is not used then the program will write this log to the following default location, /var/log/infra/infra.log. This file must be both readable and writable by the script.

`-v | --level <DEBUG|INFO|WARNING|ERROR|CRITICAL>`

The argument to the log-level flag must be one of the options shown. The options are in order of verbosity with DEBUG providing the most output. If this option is not used then the program will default to logging at the INFO level (will log all events except those pertaining to DEBUG).


## Setting up a Development and Testing Environment for the Script
A predicate for sucessfully running this code is be able to log into your tenancy as a user who has the necessary privileges that will allow the starting and stopping of objects across compartments. 

Whilst it is possible to deploy and run this project from a laptop, it is anticipated that it will be run from within the user's tenancy in OCI. Assuming this will be the case, then in addition to the above predicate the following will also be required: 
* A machine to host the project. This machine should ideally be in a compartment of its own, or at least in a compartment with other administrative machines.
    * The host machine does not need to be very powerful. Indeed, a compute instance from the free tier could be used. When creating a new compute instance, the free tier can be accessedd by changing from the default AMD shape to an Ampere (ARM architecture) or VM.Standard.E2.1.Micro shape. The latter can be found in the Speciality and Previous Generation choices.
* The host machine will need Python 3.6.8 or later installed as well as a scheduler such as cron.
    * When creating the host machine the default operating system (August 2023) is Oracle Linux 8. This OS image supports cron and has Python 3.6.8 pre-installed. It is therefore suggested that this is the image that should be used.
* The host machine will need to access the OCI tenancy via the internet even though the machine is hosted within the tenancy. This can be achieved by locating the host in a public subnet and providing it with a public IP address. Alternatively, it should be possible to deploy it in a private subnet so long as that subnet has a NAT Gateway attached to it. Using a private subnet is more secure given the host machine will not be directly accessible from the internet. The downside of course is that this also brings inconvenience for the genuine user/developer.

Assuming the host is using Oracle Linux 8 then a small amount of adminstrative work will be needed to deploy the project. The following assumes you will be working as the default user on the host, `opc`:

1. Either clone the code from this github repository or download the zip file and then unzip. For the purposes of development the code can be installed in the default user's (`opc`) home directory, `/home/opc`.
2. Create an `infra.json` file in the home directory. See the example above for details. It may be worth creating a few sacrificial compute instances and MySQL databases to test starting up and shutting down before working on objects that are performing real tasks.
3. Install the OCI CLI as detailed [here](https://docs.oracle.com/en-us/iaas/Content/API/SDKDocs/cliinstall.htm#InstallingCLI__oraclelinux8) 
4. The default location for the log file is `/var/log/infra/infra.log`, however this logfile won't be in place and the code will fail without it. There are two options to overcome this issue: either create a log file in the home directory (use `touch` to create an empty file) and then use the `-l` flag as described in [usage](usage); or create the log file in the default directory as shown below.
```console
opc@myhost$ sudo mkdir -p /var/log/infra
opc@myhost$ sudo touch /var/log/infra/infra.log
opc@myhost$ sudo chown opc /var/log/infra/infra.log 
```

## Testing
Some suggested tests.

The first time you run the code it will take a little time to complete. This because Python will byte-compile the code and store it in `__pycache__`. Subsequent runs will be much faster because they will make use of this compiled code.

The following should all return the help page. Note that `-h` overrides `-a` regardless where it is positioned on the command line.

```console
opc@myhost$ cd ~
opc@myhost$ ls
infraArgs.py  infra.json  infraMgr.py  README.md
opc@myhost$ python infraMgr.py
opc@myhost$ python infraMgr.py -h
opc@myhost$ python infraMgr.py --help
opc@myhost$ python infraMgr.py -h -a START
opc@myhost$ python infraMgr.py -a START -h
```

Now run some tests that stop and start the objects in the infrastructure file. If you are using the default settings then you should only need to specify `-a START` or `-a STOP`. At this stage keep don't exclude any objects from being stopped or started. After each run have a look in the log to see what has happened. Correlate this with what is happening in the OCI Console. Note that whilst the code executes quickly all it is doing is sending requests to OCI. The actual start and stopping of objects in OCI will take longer. For example a compute instance can be stopped/started in under a minute whereas a database may take more than a few minutes.   

```console
opc@myhost$ python infraMgr.py -a STOP
opc@myhost$ tail -f /var/log/infra/infra
# Go to the OCI Console and wait until all objects have been stopped before proceeding
opc@myhost$ python infraMgr.py -a START
opc@myhost$ tail -f /var/log/infra/infra
# Go to the OCI Console and wait until all objects have been started before proceeding
opc@myhost$ python infraMgr.py --action STOP
opc@myhost$ tail -f /var/log/infra/infra
# Immediately run the following request - you should see warnings in the log file
opc@myhost$ python infraMgr.py --action START
opc@myhost$ tail -f /var/log/infra/infra
```

Once all the objects have been started, edit the infrastructure file and set `exclude` to `true` for some of the objects and then run the following commands (waiting for the OCI tasks to complete between runs). Using the log and the 

```console
opc@myhost$ python infraMgr.py -a STOP
opc@myhost$ tail -f /var/log/infra/infra
# Go to the OCI Console and wait until all non-excluded objects have been stopped before proceeding
opc@myhost$ python infraMgr.py -a START
opc@myhost$ tail -f /var/log/infra/infra
```

Return the infrastructure file to its original state, then run the following command to investigate what DEBUG logging level provides:

```console
opc@myhost$ python infraMgr.py -a STOP -v DEBUG
opc@myhost$ tail -f /var/log/infra/infra
```

Other test suggestions:
* Investigate the optional flags changing the log, etc.
* Create another infrastructure file and run tests using it, e.g. `python infraMgr.py -a STOP -i alt-infra.json`
* Any other tests you deem necessary. Remember is no warranty associated with this software; you use it entirely at your own risk.
 
## Packaging and Running Options
In its current development form the `infraMgr.py` file must be deployed in a directory with the `infraArgs.py` file otherwise the dependencies inferred by the `from infraArgs import InfraArgs` and `from infraArgs import InfraArgsError` lines will not be met. Further, a Python interpreter (version 3.6.8) or later will need to be installed on the machine that this script is to run on. As has already been demonstrated to run the script python must be explicitly invoked on the command line, i.e. `python infraMgr.py`. However, by entering `#!/usr/bin/python` on the first line of the `infraMgr.py` file as shown below

```python
#!/usr/bin/python
import getopt
import json
import logging
...
```
and then changing the permissions on this file to make it executable, it is possible to remove the need for `python` on the command line, for example

```console
opc@myhost$ chmod 0744 infraMgr.py
opc@myhost$ ls -l infraMgr.py
opc@myhost$ ./infraMgr.py --help

  Usage
  =====
  There are two modes of usage: seeking help and performing an action. When
  ...
opc@myhost$ 
```

An alternative to deploying in the above form is to use Python utilities that will compile and link the code into a single native executable binary making deployment super-simple. `pyinstaller` is a utility that can create a single executable binary, but it first needs to be installed (as well as its dependency, `wheel`) on the development machine

```console
opc@myhost$ sudo python -m pip install wheel
opc@myhost$ sudo python -m pip install pyinstaller
```

Once installed the binary is created (and stored in a directory called dist) as follows
```console
opc@myhost$ pyinstaller --onefile infraMgr.py
opc@myhost$ ls -l
total 16
drwxrwxr-x. 2 opc opc   22 Aug 25 13:50 dist
-rw-rw-r--. 1 opc opc 1817 Aug 25 08:54 infra.json
-rw-rw-r--. 1 opc opc 9952 Aug 25 08:53 infraMgr.py
drwxrwxr-x. 2 opc opc   69 Aug 25 13:50 __pycache_
opc@myhost$ ls -l dist
total 28524
-rwxr-xr-x. 1 opc opc 29206744 Aug 25 13:50 infraMgr
opc@myhost$   

A point to note is the executable binary in dist, `infraMgr`, is only executable on a machine of the same architecture. For example the following two excerpts show a binary that has been created on an x86-64 machine (AMD/Intel) and a binary that has been created on an ARM machine. An ARM binary won't run on an AMD or Intel machine, and an x86-64 won't run on an ARM machine.

x86-64 machine:
```console
opc@myhost$ cd dist
opc@myhost$ file infraMgr
infraMgr: ELF 64-bit LSB executable, x86-64, version 1 (SYSV), dynamically linked, interpreter /lib64/ld-linux-x86-64.so.2, for GNU/Linux 3.2.0, BuildID[sha1]=ac12c327d5ac787df7fdbcae3da47d49e83924eb, stripped
opc@myhost$
```
ARM machine
```console
opc@arm$ file infraMgr
infraMgr: ELF 64-bit LSB executable, ARM aarch64, version 1 (SYSV), dynamically linked, interpreter /lib/ld-linux-aarch64.so.1, for GNU/Linux 3.7.0, BuildID[sha1]=84cc055ae3f76860840a6205b7d8abe6b6f4a5b7, stripped
opc@arm$
```

## Scheduled Running in Production

It is assumed that this software will be integrated with the `cron` scheduler in order to schedule automatic stopping and starting out of office hours. Oracle Linux 8 `cron` is relatively easy to use so long as you are familiar with either the `vi` or `nano` editors. 

By default, Oracle Linux 8 cron will use `vi`. However, the cron utility must be edited using the `crontab -e` command, thereafter use `vi` commands to insert, append, write and quit. If `vi` is not to your liking, use the `nano` utility by running `env=EDITOR=nano crontab -e`

Each (linux) user has their own crontab and ability to schedule runs. If a user other than `opc` is used, then be sure to check/change ownerships as appropriate for the log and infrastructure files.

In the example below the executable binary, created in [Packaging and Running Options](Packaging and Running Options), is copied to a more production-like destination, together with the infrastructure file. The crontab for opc is then edited such that a `START` is scheduled at 06:00 (given by the `O` for minute and `6` for hour at the start of the crontab line) on Monday, Tuesday, Wednesday, Thursday and Friday (given by the `1-5` to indicate the days of the week when the schedule should run). A full path to the infraMgr binary is provided and because the binary has been separated from the infrastructure file that too has been specified (using the `-i` flag). Given this schedule will be run by the `opc` user the log has been left at the default location (i.e. `/var/log/infra/infra.log` which is already owned by `opc`). Similarly, the OCI config file has been left in its default location (i.e. `/home/opc/.oci/config`). The second line of the crontab schedules a stop at 20:00 (given by the `0` for minute and `20` for hour at the start of the crontab line) to occur on weekdays. 

```console
opc@myhost$ sudo mkdir -p /usr/local/infra
opc@myhost$ sudo mkdir -p /usr/local/infra/bin
opc@myhost$ sudo mkdir -p /usr/local/infra/data
opc@myhost$ sudo chown -R opc /usr/local/infra 
opc@myhost$ cp /home/opc/dist/infraMgr /usr/local/infra/bin
opc@myhost$ cp /home/opc/infra.json /usr/local/infra/data
opc@myhost$ crontab -e
0 6 * * 1-5 /usr/local/infra/bin/infraMgr -i /usr/local/infra/data/infra.json -a START
0 20 * * 1-5 /usr/local/infra/bin/infraMgr -i /usr/local/infra/data/infra.json -a STOP
opc@myhost$
``` 
A final point to note: check the date on the host (use the `date` command) because it may not reflect daylight saving. For example a host in the London region will be set to GMT meaning it is one hour less than British Summer Time.  


## Extendability - Future Improvements
Here are some suggestions that may improve the existing script:

1. Database backup before shutdown
You may wish to backup a database immediately prior to shutting it down. In order to backup a MySQL Database the [oci.mysql.DbBackupsClient](https://docs.oracle.com/en-us/iaas/tools/python/2.110.2/api/mysql/client/oci.mysql.DbBackupsClient.html#oci.mysql.DbBackupsClient) API must be used.
2. Database slow shutdown
The current code shuts (stops) MySQL databases down in `FAST` mode. This is the default mode for on-premise MySQL databases (see https://dev.mysql.com/doc/refman/8.0/en/innodb-parameters.html#sysvar_innodb_fast_shutdown). Other modes that can be used are `SLOW` and `IMMEDIATE`. Immediate will crash the database and as such is not recommended for use in the script. Slow will do a full purge and change buffer merge before shutting down. In on-premise MySQL Databases slow is typically used before an upgrade to a new version.   
3. Compute instance soft stop
The current code powers-off a compute instance by calling the `oci.core.ComputeClient`'s `instance_action()` function with a `STOP` parameter. A compute instance can be shutdown more gently using the `SOFTSTOP` parameter, however, it will mean the instance will take approximately 15 minutes to shutdown. Please see https://docs.oracle.com/en-us/iaas/tools/python/2.110.1/api/core/client/oci.core.ComputeClient.html#oci.core.ComputeClient.instance_action for more details and options.
4. Wait for response / retry
The APIs being called in this script effectively create REST calls (run in `DEBUG` mode and you will see the `GET` and `POST` calls being made). REST is an asynchronous method of programming, meaning you make a request and then immediately move on to the next task/line of code without waiting for the request to be completed. As such, you cannot be sure that the request will be actioned in the way you want unless you wait an amount of time and then run a status query (i.e. poll the status of an object until it reaches the desired state). On the face of it polling seems a sensible way forward. However, it will result in a lot of code and and not really buy you much in return. For example: where in the code are you going to implement polling? If you implement it immediately after each call to start or stop an instance then it will have the affect of delaying the requests to other instances. It may make more sense to poll after all requests have been made but then you will need to decide what you log, how many polls you make before you abort and whether you want to implement retries (if at all possible).
