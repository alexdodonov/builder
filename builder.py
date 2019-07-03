#
#    Repository: https://gitlab.com/aeon.org/builder
#
#    Installation:
#
#    Download builder.py and put in your PYTHONPATH. That's it! )
#
#    First script
#
#    Create deploy.json file with the content in the example below:
#
#    {
#        "deploy" : {
#            "host" : "your-ftp-host" , "user" : "your-ftp-user" , 
#            "password" : "your-ftp-password" , "path" : "path-on-your-ftp-server"
#        } , 
#        "order" : [
#            { "step" : "deploy" , "type" : "ftp" }
#        ]
#    }
#
#    Then create script deploy.py with the below code:
#
#    import builder
#    builder.run()
#
#    When you run this script - it will deploy all the files from the directory in wich it was run
#
#    More documentation can be found here: https://gitlab.com/aeon.org/builder/wikis/builder.py-home
#
#    If you have any questions or advises - feel free to contact with the author by email alexey@dodonov.pro
#    Or create ticket here https://gitlab.com/aeon.org/builder/issues
#

import ftplib , os , io , sys , subprocess , shutil , json , hashlib , re

from subprocess import check_output
from datetime import datetime
from datetime import time
from shutil import copyfile
from os import walk
from os.path import splitext , join , split

#
#    Settings
#
service_folders = [
    './conf', './tests', './tmp', './vendor', './vendor/{service-name}', './vendor/{service-name}/conf',
    './vendor/{service-name}/include', './vendor/{service-name}/include/php', './vendor/{service-name}/include/js',
    './vendor/{service-name}/tests', './vendor/{service-name}/vendor', './vendor/{service-name}/vendor/{service-name}-logic',
    './vendor/{service-name}/vendor/{service-name}-logic/tests' , 
    './dns' , './dns/conf' , './dns/include' , './dns/include/php' , 
    './vendor/{service-name}/vendor/{service-name}-model' , './.git/info'
]

common_service_file_templates = {
    './.git/info/exclude' : "# git ls-files --others --exclude-from=.git/info/exclude\n\
# Lines that start with '#' are comments.\n\
# For a project mostly in C, the following would be a good set of\n\
# exclude patterns (uncomment them if you want to use them):\n\
# *.[oa]\n\
# *~\n\
\n\
# some Eclipse staff\n\
.settings/\n\
.buildpath\n\
.project\n\
.pydevproject\n\
tmp/\n\
__pycache__/" , 
    './.htaccess': "# show php errors\nphp_flag display_startup_errors on\nphp_flag display_errors on\nphp_flag html_errors on\n\n<Limit GET POST PUT DELETE>\n  Allow from all\n</Limit>\n\n# use mod_rewrite for pretty URL support\nRewriteEngine on\n\nRewriteRule ^data/files/(.*)$ data/files/$1 [L]\n\nRewriteRule ^vendor/(.*).css$ vendor/$1.css [L]\nRewriteRule ^res/css/(.*)$ res/css/$1 [L]\n\nRewriteRule ^vendor/(.*).js$ vendor/$1.js [L]\nRewriteRule ^res/js/(.*)$ res/js/$1 [L]\n\nRewriteRule ^vendor/(.*).woff2$ vendor/$1.woff2 [L]\nRewriteRule ^res/fonts/(.*)$ res/fonts/$1 [L]\n\nRewriteRule ^vendor/(.*).(jpg|jpeg)$ vendor/$1.$2 [L]\nRewriteRule ^res/images/(.*)$ res/images/$1 [L]\n\nRewriteRule ^res/images/(.*)$ res/images/$1 [L]\nRewriteRule ^([a-z0-9A-Z_\/\.\-\@%\ :,]+)/?(.*)$ index.php?r=$1&%{QUERY_STRING} [L]\nRewriteRule ^/?(.*)$ index.php?r=index&%{QUERY_STRING} [L]" , 
    './build.py' : "import builder\n\nbuilder.run()",
    './vendor/{service-name}/test-unit.json' : "{\n\t\"tests\": [\n\t\t\"./tests\"\n\t]\n}",
    './vendor/{service-name}/test-unit.py' : "import builder\n\nbuilder.run()" ,
    './test-service.json' : "{\n\t\"tests\": [\n\t\t\"--filter {service-class-name}ServiceTest ./tests\"\n\t]\n}" ,
    './test-service.py' : "import builder\n\nbuilder.run()" ,
    './vendor/{service-name}/vendor/{service-name}-logic/test-unit.json' : "{\n\t\"tests\": [\n\t\t\"./tests\"\n\t]\n}",
    './vendor/{service-name}/vendor/{service-name}-logic/test-unit.py' : "import builder\n\nbuilder.run()" , 
    './dns/records.php' : "<?php\nrequire_once (__DIR__ . '/include/php/dns-utils.php');\n\n// setup environment\nglobal $argv;\n\nif (isset($_SERVER['HTTP_HOST']) && $_SERVER['HTTP_HOST'] == 'ft-srv') {\n\tset_config('ft');\n\t} elseif (isset($_SERVER['HTTP_HOST']) && ($_SERVER['HTTP_HOST'] == 'localhost' || $_SERVER['HTTP_HOST'] == 'local-srv')) {\n\tset_config('local');\n} elseif ($argv !== null && in_array('local', $argv)) {\n\tset_config('local');\n} else {\n\tset_config('prod');\n}\n\nrequire_once (__DIR__ . '/conf/conf.php');\n\n?>" , 
    './dns/include/php/dns-utils.php' : "<?php\n\n/**\n *    Method returns service setting.\n */\nfunction get_dns_str($Service, $Key1 = false, $Key2 = false)\n{\n\tglobal $DNSRecords;\n\n\tif (isset($DNSRecords[$Service])) {\n\t\tif (is_string($DNSRecords[$Service])) {\n\t\t\treturn ($DNSRecords[$Service]);\n\t\t} else {\n\t\t\tif ($Key1 !== false) {\n\t\t\t\tif ($Key2 !== false) {\n\t\t\t\t\treturn ($DNSRecords[$Service][$Key1][$Key2]);\n\t\t\t\t} else {\n\t\t\t\t\treturn ($DNSRecords[$Service][$Key1]);\n\t\t\t\t}\n\t\t\t} else {\n\t\t\t\treturn ($DNSRecords[$Service]);\n\t\t\t}\n\t\t}\n\t} else {\n\t\tthrow (new Exception('Field "' . $Key1 . '" for "' . $Service . '" service was not set in the DNS'));\n\t}\n}\n\n/**\n * Method sets environment config.\n */\nfunction set_config($ConfigName)\n{\n\tif ($ConfigName == 'prod') {\n\t\tfile_put_contents(__DIR__ . '/../../conf/conf.php', file_get_contents(__DIR__ . '/../../conf/conf-prod.php'));\n\t} elseif ($ConfigName == 'ft') {\n\t\tfile_put_contents(__DIR__ . '/../../conf/conf.php', file_get_contents(__DIR__ . '/../../conf/conf-ft.php'));\n\t} else {\n\t\tfile_put_contents(__DIR__ . '/../../conf/conf.php', file_get_contents(__DIR__ . '/../../conf/conf-local.php'));\n\t}\n}\n\n?>" , 
    './dns/conf/conf-local.php' : "<?php\n$DNSRecords = [\n\t'auth' => 'http://auth-srv',\n\t'author' => 'http://author-srv',\n];\n\nfunction get_dns_records()\n{\n\tglobal $DNSRecords;\n\n\treturn ($DNSRecords);\n}\n\n?>" , 
    './dns/conf/conf-ft.php' : "<?php\n$DNSRecords = [\n\t'auth' => 'http://auth-srv',\n\t'author' => 'http://author-srv',\n];\n\nfunction get_dns_records()\n{\n\tglobal $DNSRecords;\n\n\treturn ($DNSRecords);\n}\n\n?>" , 
    './dns/conf/conf-prod.php' : "<?php\n$DNSRecords = [\n\t'auth' => 'http://auth-srv',\n\t'author' => 'http://author-srv',\n];\n\nfunction get_dns_records()\n{\n\tglobal $DNSRecords;\n\n\treturn ($DNSRecords);\n}\n\n?>" ,  
}

service_file_templates = {
    './index.php' : "<?php\nrequire_once( './vendor/service/include/php/include.php' );\nrequire_once( './vendor/anscript/vendor/{service-name}-logic/{service-name}-logic.php' );\nrequire_once( './vendor/{service-name}/{service-name}.php' );\n\nService::launch('{service-class-name}');\n\n?>",
    './build.json' : "{\n\t\"vendor-repo\" : [\n\t\t{\n\t\t\t\"vendors\" : [ \n\t\t\t\t\"dns-client\"\n\t\t\t] , \n\t\t\t\"path\" : \"D:/job/YandexDisk/enterprise/\"\n\t\t} , \n\t\t{\n\t\t\t\"vendors\" : [ \n\t\t\t\t\"router\" , \"service\"\n\t\t\t] , \n\t\t\t\"path\" : \"D:/job/YandexDisk/mezon/vendor/\"\n\t\t}\n\t]\n}",
    './vendor/{service-name}/tests/{service-class-name}UnitTest.php' : "<?php\n\n/**\n * Unit test \n * @author Admin\n */\nclass {service-class-name}UnitTest extends PHPUnit\Framework\TestCase\n{\n}\n\n?>",
    './tests/{service-class-name}ServiceTest.php' : "<?php\n\
require_once (__DIR__ . '/../dns/records.php');\n\
\n\
require_once (__DIR__ . '/../vendor/service/vendor/service-tests/service-tests.php');\n\
\n\
require_once (__DIR__ . '/../vendor/dns-client/dns-client.php');\n\
\n\
/**\n\
 * Service test\n\
 *\n\
 * @author Admin\n\
 */\n\
class {service-class-name}ServiceTest extends ServiceTests\n\
{\n\
\n\
    /**\n\
     * Constructor.\n\
     */\n\
    public function __construct()\n\
    {\n\
        parent::__construct('{service-name}');\n\
    }\n\
}\n\
\n\
?>" , 
    './vendor/{service-name}/vendor/{service-name}-logic/{service-name}-logic.php' : "<?php\n\n/**\n * Service logic\n * \n * @author \n */\nclass {service-class-name}Logic extends ServiceLogic\n{\n\n\t/**\n\t * Constructor.\n\t *\n\t * @param object $ParamsFetcher\n\t *            - Params fetcher.\n\t * @param object $SecurityProvider\n\t *            - Security provider.\n\t * @param object $Model\n\t *            - Service model.\n\t */\n\tpublic function __construct(object $ParamsFetcher, object $SecurityProvider, $Model = null)\n\t{\n\t\tparent::__construct($ParamsFetcher, $SecurityProvider, $Model);\n\t}\n}\n\n?>" ,
    './vendor/{service-name}/{service-name}.php' : "<?php\n\n/**\n * Service class.\n * \n * @author \n */\nclass {service-class-name} extends Service\n{\n\n\t/**\n\t * Constructor.\n\t *\n\t * @param mixed $ServiceTransport\n\t *            - Service's transport\n\t * @param mixed $SecurityProvider\n\t *            - Service's security provider;\n\t * @param mixed $ServiceLogic\n\t *            -\n\t *            Service's logic.\n\t * @param mixed $ServiceModel\n\t *            -\n\t *            Service's model.\n\t */\n\tpublic function __construct($ServiceTransport = 'ServiceHTTPTransport', $SecurityProvider = 'ServiceSecurityProvider', $ServiceLogic = '{service-class-name}Logic', $ServiceModel = 'ServiceModel')\n\t{\n\t\tparent::__construct($ServiceTransport, $SecurityProvider, $ServiceLogic, $ServiceModel);\n\t}\n\n\t/**\n\t * Method inits common servoce's routes.\n\t */\n\tprotected function init_common_routes()\n\t{\n\t\tparent::init_common_routes();\n\n\t\t//$this->ServiceTransport->add_route('/route/path/', 'method_name', 'GET', 'public_call', [\n\t\t//    'content_type' => 'text/html; charset=utf-8'\n\t\t//]);\n\t}\n}\n\n?>" ,
    './vendor/{service-name}/vendor/{service-name}-logic/tests/{service-class-name}LogicUnitTest.php' : "<?php\nrequire_once (__DIR__ . '/../../../../service/vendor/service-logic/service-logic.php');\nrequire_once (__DIR__ . '/../../../../service/vendor/service-logic/vendor/service-logic-unit-tests/service-logic-unit-tests.php');\nrequire_once (__DIR__ . '/../../../../service/vendor/service-model/service-model.php');\n\nrequire_once (__DIR__ . '/../{service-name}-logic.php');\n\nclass {service-class-name}LogicUnitTest extends ServiceLogicUnitTests\n{\n\t/**\n\t * Constructor.\n\t */\n\tpublic function __construct()\n\t{\n\t\tparent::__construct();\n\n\t\t$this->ClassName = '{service-class-name}Logic';\n\t}\n}\n\n?>" , 
}

crud_service_file_templates = {
    './build.json' : "{\n\t\"vendor-repo\" : [\n\t\t{\n\t\t\t\"vendors\" : [ \n\t\t\t\t\"auth-php-client\" , \"author-php-client\" , \"dns-client\" , \"auth-security-provider\"\n\t\t\t] , \n\t\t\t\"path\" : \"D:/job/YandexDisk/enterprise/\"\n\t\t} , \n\t\t{\n\t\t\t\"vendors\" : [ \n\t\t\t\t\"conf\" , \"functional\" , \"custom-client\" , \"mezon\" , \"pdo-crud\" , \"rest-client\" , \"rest-exception\" , \"router\" , \"service\" , \"singleton\" , \"template-engine\" , \"crud-service\"\n\t\t\t] , \n\t\t\t\"path\" : \"D:/job/YandexDisk/mezon/vendor/\"\n\t\t}\n\t]\n}" , 

    './index.php' : "<?php\n\
require_once ('./dns/records.php');\n\
\n\
require_once ('./vendor/conf/conf.php');\n\
require_once ('./vendor/functional/functional.php');\n\
require_once ('./vendor/service/vendor/service-client/service-client.php');\n\
require_once ('./vendor/service/vendor/service-security-provider/service-security-provider.php');\n\
\n\
require_once ('./vendor/auth-php-client/auth-client.php');\n\
require_once ('./vendor/auth-security-provider/auth-security-provider.php');\n\
\n\
require_once ('./vendor/shop-item/shop-item.php');\n\
\n\
require_once ('./vendor/shop-item/vendor/shop-item-logic/shop-item-logic.php');\n\
\n\
require_once ('./vendor/shop-item/vendor/shop-item-model/shop-item-model.php');\n\
\n\
require_once ('./conf/conf.php');\n\
\n\
// run service\n\
Service::launch('ShopItemService', 'ServiceRESTTransport', 'AuthSecurityProvider');\n\
?>" , 

    './tests/{service-class-name}ServiceTest.php' : "<?php\n\
require_once (__DIR__ . '/../dns/records.php');\n\
\n\
require_once (__DIR__ . '/../vendor/crud-service/vendor/crud-service-tests/crud-service-tests.php');\n\
\n\
require_once (__DIR__ . '/../vendor/dns-client/dns-client.php');\n\
\n\
/**\n\
 * Service test\n\
 *\n\
 * @author Admin\n\
 */\n\
class ShopItemServiceTest extends CRUDServiceTests\n\
{\n\
\n\
    /**\n\
     * Constructor.\n\
     */\n\
    public function __construct()\n\
    {\n\
        parent::__construct('{service-name}');\n\
    }\n\
}\n\
\n\
?>" ,
    './vendor/{service-name}/tests/{service-class-name}UnitTest.php' : "<?php\n\nrequire_once (__DIR__ . '/../../service/vendor/service-security-provider/service-security-provider.php');\n\nrequire_once (__DIR__ . '/../../auth-security-provider/auth-security-provider.php');\n\nrequire_once (__DIR__ . '/../../crud-service/vendor/crud-service-unit-tests/crud-service-unit-tests.php');\n\nrequire_once (__DIR__ . '/../vendor/{service-name}-logic/{service-name}-logic.php');\n\nrequire_once (__DIR__ . '/../{service-name}.php');\n\n/**\n * Unit test\n *\n * @author Admin\n */\nclass {service-class-name}UnitTest extends CRUDServiceUnitTests\n{\n\n\t/**\n\t * Constructor.\n\t */\n\tpublic function __construct()\n\t{\n\t\tparent::__construct('{service-class-name}Service');\n\t}\n}\n\n?>" , 
    './vendor/{service-name}/{service-name}.php' : "<?php\nrequire_once (__DIR__ . '/../../dns/records.php');\n\nrequire_once (__DIR__ . '/../dns-client/dns-client.php');\n\nrequire_once (__DIR__ . '/../custom-client/custom-client.php');\nrequire_once (__DIR__ . '/../rest-client/rest-client.php');\nrequire_once (__DIR__ . '/../router/router.php');\nrequire_once (__DIR__ . '/../service/service.php');\nrequire_once (__DIR__ . '/../service/vendor/service-client/service-client.php');\nrequire_once (__DIR__ . '/../service/vendor/service-logic/service-logic.php');\nrequire_once (__DIR__ . '/../service/vendor/service-rest-transport/service-rest-transport.php');\nrequire_once (__DIR__ . '/../service/vendor/service-security-provider/service-security-provider.php');\n\nrequire_once (__DIR__ . '/../crud-service/crud-service.php');\nrequire_once (__DIR__ . '/../crud-service/vendor/crud-service-logic/crud-service-logic.php');\nrequire_once (__DIR__ . '/../crud-service/vendor/crud-service-model/crud-service-model.php');\n\nclass {service-class-name}Service extends CRUDService\n{\n\n\t/**\n\t * Constructor.\n\t *\n\t * @param mixed $ServiceTransport\n\t *            - Service's transport.\n\t * @param mixed $SecurityProvider\n\t *            - Service's security provider;\n\t * @param mixed $ServiceLogic\n\t *            -\n\t *            Service's logic.\n\t * @param mixed $ServiceModel\n\t *            -\n\t *            Service's model.\n\t */\n\tpublic function __construct($ServiceTransport = 'ServiceRESTTransport', $SecurityProvider = 'ServiceMockSecurityProvider', $ServiceLogic = '{service-class-name}Logic', $ServiceModel = '{service-class-name}Model')\n\t{\n\t\t$Fields = [\n\t\t\t'id' => [\n\t\t\t\t'type' => 'integer',\n\t\t\t\t'title' => 'id'\n\t\t\t]\n\t\t];\n\n\t\tparent::__construct('{service-name}', $Fields, '{service-name}', [], $ServiceTransport, $SecurityProvider, $ServiceLogic, $ServiceModel);\n\t}\n}\n\n?>" , 
    './vendor/{service-name}/vendor/{service-name}-logic/{service-name}-logic.php' : "<?php\n\n/**\n * Service logic\n * \n * @author \n */\nclass {service-class-name}Logic extends CRUDServiceLogic\n{\n}\n\n?>" ,
    './vendor/{service-name}/vendor/{service-name}-logic/tests/{service-class-name}LogicUnitTest.php' : "<?php\nrequire_once (__DIR__ . '/../../../../functional/functional.php');\nrequire_once (__DIR__ . '/../../../../router/router.php');\nrequire_once (__DIR__ . '/../../../../service/vendor/service-logic/service-logic.php');\nrequire_once (__DIR__ . '/../../../../service/vendor/service-logic/vendor/service-logic-unit-tests/service-logic-unit-tests.php');\nrequire_once (__DIR__ . '/../../../../service/vendor/service-console-transport/service-console-transport.php');\nrequire_once (__DIR__ . '/../../../../service/vendor/service-console-transport/vendor/console-request-params/console-request-params.php');\nrequire_once (__DIR__ . '/../../../../service/vendor/service-security-provider/service-security-provider.php');\nrequire_once (__DIR__ . '/../../../../service/vendor/service-mock-security-provider/service-mock-security-provider.php');\n\nrequire_once (__DIR__ . '/../../../../crud-service/vendor/crud-service-logic/vendor/crud-service-logic-unit-tests/crud-service-logic-unit-tests.php');\n\nrequire_once (__DIR__ . '/../{service-name}-logic.php');\n\nclass {service-class-name}LogicUnitTest extends CRUDServiceLogicUnitTests\n{\n\n\t/**\n\t * Constructor.\n\t */\n\tpublic function __construct()\n\t{\n\t\tparent::__construct();\n\n\t\t$this->ClassName = '{service-class-name}Logic';\n\t}\n}\n\n?>" , 
    './vendor/{service-name}/vendor/{service-name}-logic/phpunit.xml' : "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<phpunit xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" xsi:noNamespaceSchemaLocation=\"http://schema.phpunit.de/7.0/phpunit.xsd\" backupGlobals=\"false\" colors=\"true\">\n\t<php>\n\t\t<ini name=\"error_reporting\" value=\"-1\" />\n\t</php>\n\n\t<testsuites>\n\t\t<testsuite name=\"Test Suite\">\n\t\t\t<directory>tests</directory>\n\t\t</testsuite>\n\t</testsuites>\n\n\t<filter>\n\t\t<whitelist>\n\t\t\t<directory>./</directory>\n\t\t\t<exclude>\n\t\t\t\t\t<directory>./tests</directory>\n\t\t\t</exclude>\n\t\t</whitelist>\n\t</filter>\n\n\t<logging>\n\t\t<log type=\"coverage-html\" target=\"./tmp/coverage-phpunit.html\"></log>\n\t\t<log type=\"coverage-text\" target=\"php://stdout\" showOnlySummary=\"true\"></log>\n\t</logging>\n</phpunit>" ,

    './vendor/{service-name}/vendor/{service-name}-model/{service-name}-model.php' : "<?php\n\
require_once (__DIR__ . '/../../../crud-service/vendor/crud-service-model/crud-service-model.php');\n\
\n\
/**\n\
 * Model\n\
 *\n\
 * @author Admin\n\
 */\n\
class ShopItemModel extends CRUDServiceModel\n\
{\n\
}\n\
\n\
?>" , 
    './conf/conf.php' : "<?php\n\
if (isset($_SERVER['HTTP_HOST']) && $_SERVER['HTTP_HOST'] == 'prod-srv') {\n\
    add_connection_to_config('default-db-connection', 'mysql:dbname={service-name};host=localhost', 'root', '');\n\
} elseif (isset($_SERVER['HTTP_HOST']) && ($_SERVER['HTTP_HOST'] == 'localhost' || $_SERVER['HTTP_HOST'] == '{service-name}-service.local')) {\n\
    add_connection_to_config('default-db-connection', 'mysql:dbname={service-name};host=localhost', 'root', '');\n\
} else {\n\
    add_connection_to_config('default-db-connection', 'mysql:dbname={service-name};host=localhost', 'root', '');\n\
}\n\
\n\
?>"
}

not_skippable_vendor_files = [ 
    '__pycache__' , '/tmp/' , '\\tmp\\' , '\\tmp/' , '/tmp\\' ,
    'phpMyAdmin' , '.settings' , '.buildpath' , '.project' , '.pydevproject' , '.git' , '.sass', '.map' , '.scss' , '.pyc'
]

non_deployable_files = [ 
    '__pycache__' , '/tmp/' , '\\tmp\\' , '\\tmp/' , '/tmp\\' ,
    'phpMyAdmin' , '.settings' , '.buildpath' , '.project' , '.pydevproject' , '.git' , '.sass', '.map' , '.scss' , '.pyc' ,
    '/tests/' , '.git' , '.sass', '.map' , '.scss' , '.py' , 'prod.json' , 'test.json' , 'build.json' , 'service.json' , 'unit.json' ,
    'local.json' , '.md' , 'phpunit.xml' , '/tests\\' , '\\tests/' , '\\tests\\'
]

#
#    Globals
#

ftp_connection = False

make_ftp_folder_structure_created_paths = []

run_settings = '.build'

temporary_vendors = []


#
#    Method builds folder tree
#
def select_files(root , files):
    selected_files = []

    for file in files:
        # do concatenation here to get full path 
        full_path = join(root , file)
        selected_files.append(full_path)

    return selected_files


#
#    Method builds folder tree
#
def build_recursive_dir_tree(path):
    if(os.path.isdir(path) == False):
        raise Exception('Directory ' + path + ' does not exists')

    selected_files = []

    for root , dirs , files in walk(path):
        selected_files += select_files(root , files)

    return selected_files


#
#    Method returns not skippable files
#
def not_skippable_masks_files(masks , files):
    result = []

    for file in files:
        if(not_skippable_masks_file(masks , file)):
            result.append(file)

    return(result)


#
#    Method returns true if the file is not skippable
#
def not_skippable_masks_file(masks , file):
    for mask in masks:
        if(mask in file):
            return False

    return True


#
#    Method returns last build date
#
def get_last_build_date():
    try:
        file_stream = open('./tmp/' + run_settings , 'rt')
        last_build_date = file_stream.readline()
        file_stream.close()
    except io.UnsupportedOperation:
        last_build_date = '2000-01-01 00:00:00.000000'
    except FileNotFoundError:
        last_build_date = '2000-01-01 00:00:00.000000'

    return(last_build_date)


#
#    Method returns updated files since the last build
#
def get_updated_files(path):
    # getting all files
    files = build_recursive_dir_tree(path)

    # getting date and time ofthe last build
    last_build_date = get_last_build_date()

    result = [];

    # filtering files and getting only updated ones
    for file in files:
        file_update_time = os.path.getmtime(file)
        file_update_time = datetime.fromtimestamp(file_update_time).strftime('%Y-%m-%d %H:%M:%S.%f')

        if(file_update_time > last_build_date):
            result.append(file)

    return(result)


#
# Method calculatesmd5 hashof the file
#
def md5(path):
    hash_md5 = hashlib.md5()

    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)

    return hash_md5.hexdigest()


#
#    Method returns updated files since the last build
#
def get_updated_files_ex(src_path, dst_path):
    # getting all files
    files = build_recursive_dir_tree(src_path)

    # Filtering files needed to be skipped
    files = not_skippable_masks_files(not_skippable_vendor_files , files)

    result = [];

    # filtering files and getting only updated ones
    for file in files:
        to_path = dst_path + os.path.relpath(file , src_path)

        if(os.path.isfile(to_path) == False):
            result.append(file)
        else:
            if(md5(to_path) != md5(file)):
                # copy only if src file is newer than dst one
                src_file_update_time = os.path.getmtime(file)
                src_file_update_time = datetime.fromtimestamp(src_file_update_time).strftime('%Y-%m-%d %H:%M:%S.%f')
    
                dst_file_update_time = os.path.getmtime(to_path)
                dst_file_update_time = datetime.fromtimestamp(dst_file_update_time).strftime('%Y-%m-%d %H:%M:%S.%f')
    
                if(dst_file_update_time < src_file_update_time):
                    result.append(file)

    return(result)


#
#    Function safely creates folder
#
def safe_create_folder(folder):
    try:
        os.mkdir(folder)
    except FileExistsError:
        pass;


#
#    Creating folder structure via FTP
#
def make_ftp_folder_structure(ftp_session , path):
    path = path.replace('/' , '\\')

    if(path in make_ftp_folder_structure_created_paths):
        return
    else:
        make_ftp_folder_structure_created_paths.append(path)

    path = path.split('\\')

    for i in range(0 , len(path)):
        try:
            ftp_session.mkd('/'.join(path[ 0 : i + 1 ]))
        except ftplib.error_perm:
            pass


#
#    Exception class
#
class FTPError(Exception):

    def __init__(self , message):
        self.Message = message


#
#    Method establishes FTP connection and moves to the directory
#
def make_ftp_connection(host , login , password):
    try:
        # connecting to the server and store file
        ftp_session = ftplib.FTP(host , login , password)
    except ftplib.error_perm:
        raise Exception('Login error with login = ' + login + ' and password = ' + password)

    return(ftp_session)


#
#    Method establishes FTP connection and moves to the directory
#
def make_ftp_connection_to_path(host , login , password , server_path):
    ftp_session = make_ftp_connection(host , login , password)

    make_ftp_folder_structure(ftp_session , server_path)
    ftp_session.cwd(server_path)

    return(ftp_session)


#
#    Method copies files to the server
#
def copy_files_to_ftp(ftp_session , files , local_path , server_path):
    i = 1

    if(len(files)):
        for file in files:
            path = os.path.dirname(os.path.relpath(file , local_path))
            file_stream = open(file , 'rb')

            make_ftp_folder_structure(ftp_session , path)

            ftp_session.cwd(path.replace('\\' , '/'))
            ftp_session.storbinary('STOR ' + os.path.basename(file) , file_stream)
            ftp_session.cwd('/' + server_path)
            file_stream.close()

            print('UPLOADED: ' + str(i) + ' of ' + str(len(files)) + ' ' + file.replace('\\' , '/'))

            i += 1
    else:
        print('UPLOADED: All files are up-to-date')


#
#    Method sends sources to FTP server
#
def copy_sources_to_ftp(host , login , password , server_path , files):
    ftp_session = make_ftp_connection_to_path(host , login , password , server_path)

    copy_files_to_ftp(ftp_session , files , './' , server_path)

    ftp_session.quit()


#
#    Method returns a list of updated or all prohect's filestobe deployed
#
def get_files_to_deploy(dir , only_updated=True):
    if only_updated:
        raw = get_updated_files(dir)

    else:
        raw = build_recursive_dir_tree(dir)

    files = []

    for file in raw:
        if(not_skippable_masks_file(non_deployable_files , file)):
            files.append(file)

    return(files)


#
#    Method copies all sources to ftp server
#
def redeploy_to_ftp(host , login , password , server_path):
    files = get_files_to_deploy('./' , False);

    copy_sources_to_ftp(host , login , password , server_path , files)


#
#    Method copies diff sources to ftp server
#
def deploy_to_ftp(host , login , password , server_path):
    files = get_files_to_deploy('./' , True);

    copy_sources_to_ftp(host , login , password , server_path , files)


#
#    Method connects to the FTP server
#
def connect_to_ftp(host , login , password):
    global ftp_connection

    ftp_connection = make_ftp_connection(host , login , password)

    global make_ftp_folder_structure_created_paths

    make_ftp_folder_structure_created_paths = []


#
#    Class for getting single char from input
#
class CrossPlatformGetch:

    def __init__(self):
        try:
            self.impl = _GetchWindows()
        except ImportError:
            self.impl = _GetchUnix()
        self.impl()


#
#    Getting char method
#
def getch():
    CrossPlatformGetch()


#
#    Getting single char from input on Unix
#
class _GetchUnix:

    def __init__(self):
        import tty

    def __call__(self):
        import tty, termios
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd , termios.TCSADRAIN , old_settings)
        return ch


#
#    Getting single char from input on Windows
#
class _GetchWindows:

    def __init__(self):
        import msvcrt

    def __call__(self):
        import msvcrt
        return msvcrt.getch()


#
#    Method runs phpunit
#
def run_phpunit(path , module=''):
    try:
        result = check_output('php c:/php/phpunit.phar ' + path , shell=True)
        matches = re.search('Lines:[ ]{1,}([0-9]{1,2})\.([0-9]{1,2})\%', str(result, 'utf-8'))
        target_threshold = 75
        if(not(matches is None) and int(matches.group(1)) < target_threshold):
            raise Exception('Module test ' + ('' if module == '' else module + ' ') + 'failed. Target threshold is ' + str(target_threshold) + '. Actual is ' + matches.group(1))
        print('SUCCESS : Module ' + ('' if module == '' else module + ' ') + 'checked')
    except subprocess.CalledProcessError as Err:
        print(Err.output.decode('utf-8' , 'ignore').replace('\n' , "\n"))
        print('FAILED  : Module check failed')
        raise Exception('Module test failed')


#
#    Final actions
#
def finish_actions():
    safe_create_folder('./tmp/')

    file_stream = open('./tmp/' + run_settings , 'wt')
    file_stream.write(str(datetime.now()))
    file_stream.close()

    clear_temporary_vendors()


#
#    Finish method body
#
def finish_verbose():

    finish_actions()

    # final messaging
    print("Success!")
    sys.exit()


#
#    Finishing building
#
def finish():

    finish_actions()

    # final messaging
    print("Success!")
    getch()
    sys.exit()


#
#    Method finishes building process
#
def finish_building():
    finish()


#
#    Final messaging
#
def final_messaging(error_message):
    print(error_message)
    getch()
    sys.exit(1)


#
#    Method cancels building
#
def cancel(error_message):
    clear_temporary_vendors()

    # final messaging
    final_messaging(error_message)


#
#    Method cancels building
#
def cancel_verbose(error_message):
    clear_temporary_vendors()

    # final messaging
    print(error_message)
    sys.exit(1)


#
#    Method cancels building
#
def cancel_building(error_message):
    cancel(error_message)


#
#    Uploading vendor sources
#
def upload_component_sources(files , component , src_path , dst_path , action):
    if(len(files) == 0):
        print('SKIPPED : ' + component + ' ' + action)
        return

    print(action + ' : ' + src_path + component)
    counter = 1;

    for file in files:
        print('UPLOADED: ' + str(counter) + ' of ' + str(len(files)))

        if(not_skippable_masks_file(not_skippable_vendor_files , file)):
            try:
                to_path = dst_path + os.path.relpath(file , src_path)
                os.makedirs(os.path.dirname(to_path) , exist_ok=True)
                copyfile(file , to_path)
            except FileNotFoundError as Err:
                raise Exception(dst_path + file.lstrip('./\\'))

        counter = counter + 1


#
#    Uploading vendor sources
#
def upload_component_sources_with_skippped(files , component , src_path , dst_path , action):
    if(len(files) == 0):
        print('SKIPPED : ' + component + ' ' + action)
        return

    print(action + ' : ' + src_path + component)
    counter = 1;

    for file in files:
        print('UPLOADED: ' + str(counter) + ' of ' + str(len(files)))

        # Here we do not check do we need to skip file
        try:
            to_path = dst_path + os.path.relpath(file , src_path)
            os.makedirs(os.path.dirname(to_path) , exist_ok=True)
            copyfile(file , to_path)
        except FileNotFoundError as Err:
            raise Exception(dst_path + file.lstrip('./\\'))

        counter = counter + 1


#
#    Method performs action for the component
#
def process_component(component , src_path , dst_path , action , only_updated=True):
    # create vendor folder
    safe_create_folder(dst_path)

    # getting files
    if(only_updated):
        files = get_updated_files_ex(src_path + component + '/' , dst_path + component + '/')
    else:
        files = build_recursive_dir_tree(src_path + component + '/')

    # uploading sources
    upload_component_sources_with_skippped(files , component , src_path , dst_path , action)


#
#    Method processes self update
#
def process_self(component , src_path , dst_path , action , only_updated=True):
    # getting files
    if(only_updated):
        files = get_updated_files(src_path + '/')
    else:
        files = build_recursive_dir_tree(src_path + '/')

    # uploading sources
    upload_component_sources(files , component , src_path , dst_path , action)


#
#    Method recopies vendor.
#
def copy_vendors(vendors , src_path):
    for vendor in vendors:
        process_component(vendor , src_path , './vendor/' , 'REFRESH' , True)


#
#    Method processess temporary repo step
#
def process_temporary_repo_step(batches):
    for batch in batches:
        install_temporary_vendors(batch.get('vendors') , batch.get('path') , batch.get('dst-path' , './vendor/'))


#
#    Method processess tests step
#
def process_tests_step(tests):
    for test in tests:
        run_phpunit(test , os.path.basename(os.path.dirname(test)))


#
#    Method processess shell step
#
def process_shell_step(shell):
    for command in shell:
        print('RUN SHELL: ' + command)
        check_output(command , shell=True)


#
#    Method executes script's commands ina special way
#
def run_steps_in_custom_order(config):
    for step in config.get('order'):
        if(step.get('type') == 'temporary-repo'):
            process_temporary_repo_step(config.get(step.get('step')))

        if(step.get('type') == 'tests'):
            process_tests_step(config.get(step.get('step')))

        if(step.get('type') == 'shell'):
            process_shell_step(config.get(step.get('step')))

        if(step.get('type') == 'ftp'):
            if 'mode' in config.get(step.get('step')).keys() and config.get(step.get('step')).get('mode') == 'redeploy':
                redeploy_to_ftp(
                    config.get(step.get('step')).get('host') , config.get(step.get('step')).get('user') ,
                    config.get(step.get('step')).get('password') , config.get(step.get('step')).get('path')
                )
            else:
                deploy_to_ftp(
                    config.get(step.get('step')).get('host') , config.get(step.get('step')).get('user') ,
                    config.get(step.get('step')).get('password') , config.get(step.get('step')).get('path')
                )


#
#    Method runs JSON config
#
def run_script(config):
    if('order' in config):
        run_steps_in_custom_order(config)

    if('repo' in config):
        for batch in config.get('repo'):
            copy_vendors(batch.get('vendors') , batch.get('path'))

    if('vendor-repo' in config):
        for batch in config.get('vendor-repo'):
            copy_vendors(batch.get('vendors') , batch.get('path'))

    if('self-repo' in config):
        process_self('SELF' , config.get('self-repo').get('path') , './' , 'COPY' , False)

    if('temporary-repo' in config):
        process_temporary_repo_step(config.get('temporary-repo'))

    if('tests' in config):
        process_tests_step(config.get('tests'))

    if('ftp' in config):
        if 'mode' in config.get('ftp').keys() and config.get('ftp').get('mode') == 'redeploy':
            redeploy_to_ftp(
                config.get('ftp').get('host') , config.get('ftp').get('user') ,
                config.get('ftp').get('password') , config.get('ftp').get('path')
            )
        else:
            deploy_to_ftp(
                config.get('ftp').get('host') , config.get('ftp').get('user') ,
                config.get('ftp').get('password') , config.get('ftp').get('path')
            )


#
#    Run method body
#
def run_body():
    startup()

    file_name = os.path.splitext(os.path.basename(sys.argv[ 0 ]))[ 0 ]

    global run_settings
    run_settings = '.' + file_name

    with open('./' + file_name + '.json') as JSONFile:  
        config = json.load(JSONFile)

    run_script(config)


#
#    Method configures/deploys project
#
def run():
    try:
        run_body()

        finish()

    except Exception as Err:
        cancel(Err)


#
#    Method runs script in verbose way
#
def run_verbose():
    try:
        run_body()

        finish_verbose()

    except(Exception) as Err:
        cancel_verbose(Err)


#
#    Method reads service name
#
def read_service_name(message):
    print(message)

    service_name = os.read(0, 100)
    service_name = str(service_name, "ascii").lower().strip()

    return service_name


#
#
#
def create_service_folders(service_name):
    # Creating folders
    global service_folders

    for folder_path in service_folders:
        folder_path = folder_path.replace('{service-name}', service_name)
        safe_create_folder(folder_path)


#
#    Method creates files from templates
#
def create_files_from_templates(templates, service_name, service_class_name):
    for key in templates:
        file_path = key.replace('{service-name}', service_name)
        file_path = file_path.replace('{service-class-name}', service_class_name)

        if(os.path.isfile(file_path) == False):
            file_content = templates[key].replace('{service-name}', service_name)
            file_content = file_content.replace('{service-class-name}', service_class_name)
            with open(file_path, 'w') as file:
                file.write(file_content)


#
#    Method creates common service's parts
#
def init_common_service_part():
    startup()

    service_name = read_service_name("Input name of the service")

    create_service_folders(service_name)

    parts = service_name.split("-")
    service_class_name = ''
    for part in parts:
        service_class_name = service_class_name + part.capitalize()

    # creating common files
    global common_service_file_templates

    create_files_from_templates(common_service_file_templates, service_name, service_class_name)

    return service_name , service_class_name


#
#    Method runs final initializations
#
def final_init(config):
    run_script(json.loads(config))

    print("Success!")


#
#    Method inits new service
#
def init_service():
    try:
        service_name , service_class_name = init_common_service_part()

        # creating service files
        global service_file_templates

        create_files_from_templates(service_file_templates, service_name, service_class_name)

        final_init(service_file_templates['./build.json'])

    except Exception as Err:
        final_messaging(Err)


#
#    Method creates crud service
#
def init_crud_service():
    try:
        service_name , service_class_name = init_common_service_part()

        # creating CRUD service files
        global crud_service_file_templates

        create_files_from_templates(crud_service_file_templates, service_name, service_class_name)

        final_init(crud_service_file_templates['./build.json'])

    except Exception as Err:
        final_messaging(Err)


#
#    Method installs vendor for temporary usage
#
def install_temporary_vendor(vendor , src_path , dst_path='./vendor/'):

    # create vendor folder
    safe_create_folder(dst_path)

    # getting ALL files
    files = build_recursive_dir_tree(src_path + vendor + '/')

    # uploading sources
    upload_component_sources(files , vendor , src_path , dst_path , 'INSTALL')

    # store processed component so it can be rolled back
    temporary_vendors.append(dst_path + vendor)


#
#    Method installs temporary vendors for the service
#
def install_temporary_vendors(vendors , src_path , dst_path='./vendor/'):
    for vendor in vendors:
        install_temporary_vendor(vendor , src_path , dst_path)


#
#    Method lears temporary vendors
#
def clear_temporary_vendors():
    try:
        for vendor in temporary_vendors:
            print('UNINSTALL: ' + vendor)

            clear_directory(vendor + '/')

        os.rmdir(vendor)
    except:
        pass


#
#    Method clears directory
#
def clear_directory(dir):
    try:
        for file in os.listdir(dir):
            file_path = os.path.join(dir , file)
            try:
                if os.path.isfile(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path): shutil.rmtree(file_path)
            except Exception as e:
                print(e)
    except FileNotFoundError as Err:
        pass

    shutil.rmtree(dir , ignore_errors=True)


#
#    Method setups script
#
def startup():
	# os.chdir( os.getcwd() )
    os.chdir(os.path.dirname(sys.argv[ 0 ]))
