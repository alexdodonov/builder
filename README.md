# builder

Micro framework for creating building and deployment scripts

## Installation:

Download builder.py and put in your PYTHONPATH. That's it! )

## First script

Create deploy.json file with the content in the example below:

```
{
    "deploy" : {
        "host" : "your-ftp-host" , "user" : "your-ftp-user" , 
        "password" : "your-ftp-password" , "path" : "path-on-your-ftp-server"
    } , 
    "order" : [
        { "step" : "deploy" , "type" : "ftp" }
    ]
}
```

Then create script deploy.py with the below code:

```
import builder
builder.run()
```

When you run this script - it will deploy all the files from the directory in wich it was run

It is also possible to deploy on multiple servers:

```
{
    "deploy1" : {
        "host" : "your-ftp-host-1" , "user" : "your-ftp-user-1" , 
        "password" : "your-ftp-password-1" , "path" : "path-on-your-ftp-server-1"
    } , 
    "deploy2" : {
        "host" : "your-ftp-host-2" , "user" : "your-ftp-user-2" , 
        "password" : "your-ftp-password-2" , "path" : "path-on-your-ftp-server-2"
    } , 
    "order" : [
        { "step" : "deploy1" , "type" : "ftp" } , 
        { "step" : "deploy2" , "type" : "ftp" }
    ]
}
```

The config above tells Builder that it is necessary to deploy project on two servers via FTP.

## Running tests

Builder allows you tu run PHPUnit tests. To do this just create another JSON config test.json:

```
{
    "tests": [
        "--filter PlugServiceTest ./tests"
    ]
}
```

And then create test.py with the same content as deploy.py in the above example. Then run test.py and rest )

More documentation can be found here: [https://gitlab.com/aeon.org/builder/wikis/builder.py-home](https://gitlab.com/aeon.org/builder/wikis/builder.py-home)

If you have any questions or advises - feel free to contact with the author by email [alexey@dodonov.pro](mailto:alexey@dodonov.pro)

Or create ticket here [https://gitlab.com/aeon.org/builder/issues](https://gitlab.com/aeon.org/builder/issues)