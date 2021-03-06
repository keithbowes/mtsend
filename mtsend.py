#!/usr/bin/env python3

'''\
Usage: 
    mtsend.py [action] [options]

Actions:
    -A name     Add a new category.
    -B site     List all the blogs you can access in [site]. Site has to be in
                the configuration file.
    -C          Print out a list of existing categories.
    -D catid    Delete an existing category.
    -E postid   Edit an old post. It will read the post entry from the
                standard input, in Movable Type's import/export format, and
                then save it back to the server. If the value is '-', then it
                will try to detect the postid from the input message itself.
    -G postid   Retrieve/get post from the blog. If the value is '-', it will
                then try to get the most recent blog entry. Retrieved entry
                will be printed to the standard output.
    -L num      List the most recent [num] posts.
    -N          Posting a new blog. The entry, in the Movable Type
                import/export format, is read from the standard input.
    -P postid   List out trackback pings to this post.
    -R postid   Rebuild all the static files related to this entry.
    -T          List out the text filters installed on the server.
    -U filename Upload a file, reading from standard input, to the blog site,
                with destination filename provided.
    -V          Show version information.
    -X postid   Delete a post.

Options:
    -a alias    Use "alias" as the blog alias. This script will locate
                relavent site URL/username/password information using this
                alias.
    -c config   Load "config" as configuration file, instead of the default.
    -h          Display this help message.
    -q          Decrease verbose level.
    -v          Increase verbose level. Message goes to standard error.

For more information, please visit:
    http://scott.yang.id.au/2002/12/mtsendpy/
'''

__author__      = 'Scott Yang <scotty@yang.id.au>'
__copyright__   = 'Copyright (c) 2002-2005 Scott Yang'
__date__        = '2005-11-19'
__version__     = '1.1'

import configparser
import os
import platform
import re
import sys
import time
import urllib.parse
import xmlrpc.client


class MTSend(object):
    def __init__(self):
        self.alias = None
        self.input = None
        self.config = None
        self.mode = None
        self.verbose = 1
        self.rpcsrv = None
        self.site = None
        self.modeopt = None

    def execute(self):
        try:
            handler = getattr(self, 'execute_%s' % self.mode)
        except AttributeError:
            raise Exception('Unknown execution mode: %s' % self.mode)
        else:
            handler()

    def execute_a(self):
        srv = self.getRPCServer()
        srv.wp.newCategory(self.get_blogid(), self.get_username(), self.get_password(), {'name': self.modeopt})

    def execute_b(self):
        self.site = self.modeopt
        srv = self.getRPCServer()
        blogs = srv.blogger.getUsersBlogs('', self.get_username(), 
            self.get_password())
        result = [['ID', 'Blog Name', 'URL']]
        for blog in blogs:
            result.append([blog['blogid'], blog['blogName'], blog['url']])
        print_table(result)

    def execute_c(self):
        srv = self.getRPCServer()
        cts = srv.mt.getCategoryList(self.get_blogid(), self.get_username(), 
            self.get_password())
        result = []
        for cat in cts:
            result.append([cat['categoryId'], cat['categoryName']])
        sorted(result)
        result[0:0] = [['ID', 'Category Name']]
        print_table(result)

    def execute_d(self):
        srv = self.getRPCServer()
        srv.wp.deleteCategory(int(self.get_blogid()), self.get_username(), self.get_password(), int(self.modeopt))

    def execute_e(self):
        self.log(1, 'Parsing post entry from standard input...')
        post, cts, publish = parse_post()

        postid = self.modeopt
        if self.modeopt == '-':
            try:
                postid = post['postid']
            except KeyError:
                raise Exception('Cannot discover post ID from the input.')

        elif 'postid' in post and (post['postid'] != postid):
            raise Exception('Post ID does not match. ID in the input is "%s"' % \
                    post['postid'])

        srv = self.getRPCServer()
        self.log(1, 'Saving post entry "%s"...', postid)
        srv.metaWeblog.editPost(postid, self.get_username(), 
            self.get_password(), post, publish)

        cts = self._fixCategories(cts)
        if len(cts) > 0:
            self.log(1, 'Add categories "%s" to post entry "%s"...',
                ','.join([cat['categoryId'] for cat in cts]), postid)
            srv.mt.setPostCategories(postid, self.get_username(),
                self.get_password(), cts)

    def execute_g(self):
        srv = self.getRPCServer()
        if self.modeopt.lower() == '-':
            self.log(1, 'Retrieve most recent post entry...')
            post = srv.metaWeblog.getRecentPosts(str(self.get_blogid()), 
                self.get_username(), self.get_password(), 1)
            if len(post) > 0:
                post = post[0]
            else:
                raise Exception('The current blog does not have any entry.')
        else:
            self.log(1, 'Retrieve post entry "%s"...', self.modeopt)
            post = srv.metaWeblog.getPost\
                ( self.modeopt, self.get_username(), self.get_password() )

        # Get the categories of this post.
        self.log(1, 'Retrieve categories for post entry "%s"...', 
                 post['postid'])
        cts = srv.mt.getPostCategories(str(post['postid']), self.get_username(), 
            self.get_password())

        print_post(post, cts)

    def execute_l(self):
        srv = self.getRPCServer()
        try:
            num = int(self.modeopt)
        except:
            num = 0

        posts = srv.metaWeblog.getRecentPosts(self.get_blogid(), self.get_username(), 
            self.get_password(), num)
        num = len(posts)

        self.log(1, 'Retrieve "%d" recent posts...', num)
        result = [['ID', 'Date', 'Title']]
        for post in posts:
            result.append([
                post['postid'],
                time.strftime('%Y-%m-%d %H:%M:%S', 
                    decode_iso8601(post['dateCreated'])),
                post['title']
            ])

        print_table(result)

    def execute_n(self):
        self.log(1, 'Parsing post entry from standard input...')
        post, cts, publish = parse_post()
        srv = self.getRPCServer()

        self.log(1, 'Saving new post entry...')
        postid = srv.metaWeblog.newPost(self.get_blogid(), self.get_username(), 
            self.get_password(), post, publish)

        cts = self._fixCategories(cts)
        if len(cts) > 0:
            self.log(1, 'Add categories "%s" to post entry "%s"...',
                     ','.join([cat['categoryId'] for cat in cts]), postid)
            srv.mt.setPostCategories(postid, self.get_username(), 
                self.get_password(), cts)

        print(postid)

    def execute_p(self):
        srv = self.getRPCServer()
        result = [[
            val['pingTitle'],
            val['pingURL'],
            val['pingIP'],
        ] for val in srv.mt.getTrackbackPings(self.modeopt)]

        result.insert(0, ['Title', 'URL', 'IP'])
        print_table(result)

    def execute_r(self):
        srv = self.getRPCServer()
        srv.mt.publishPost(self.modeopt, self.get_username(), 
            self.get_password())

    def execute_t(self):
        srv = self.getRPCServer()
        result = []
        for val in srv.mt.supportedTextFilters():
            result.append([val['key'], val['label']])

        result.sort()
        result.insert(0, ['Key', 'Label'])
        print_table(result)

    def execute_u(self):
        srv = self.getRPCServer()
        bin = sys.stdin.read()

        self.log(1, 'Uploading "%s" (%d bytes)...', self.modeopt, len(bin))
        media_object = {
            'name': self.modeopt,
            'bits': xmlrpc.client.Binary(bin),
        }

        result = srv.metaWeblog.newMediaObject(self.get_blogid(), 
            self.get_username(), self.get_password(), media_object)

        print(result['url'])

    def execute_x(self):
        srv = self.getRPCServer()
        srv.blogger.deletePost('mtsend', self.modeopt, self.get_username(), self.get_password(), True)

    def getRPCServer(self):
        if self.rpcsrv is not None:
            return self.rpcsrv

        httptype = urllib.parse.splittype(self._getSite('url'))[0]
        transport = get_rpc_transport(httptype)

        # Default we will use 'UTF-8' encoding, if the site encoding option is
        # not provided.
        return xmlrpc.client.ServerProxy(self._getSite('url'), transport,
            self._getSite('encoding', 'UTF-8'))

    def get_blogid(self):
        return self._getBlog('blogid')

    def get_password(self):
        return self._getSite('password')

    def get_username(self):
        return self._getSite('username')

    def getConfigFile(self):
        try:
            from gi.repository import GLib
            configdirs = [GLib.get_user_config_dir()] + GLib.get_system_config_dirs()
            for configdir in configdirs:
                config = os.path.join(configdir, 'mtsend', 'mtsend.ini')
                print("Looking for configuration file %s" % config)
                if os.path.exists(config):
                    break
            assert(os.path.exists(config))
        except:
            try:
                config = os.path.join(os.environ['XDG_CONFIG_HOME'], 'mtsend', 'mtsend.ini');
                print("Looking for configuration file %s" % config)
                assert(os.path.exists(config));
            except:
                try:
                    config = os.path.join(os.environ['HOME'], '.config', 'mtsend', 'mtsend.ini')
                    print("Looking for configuration file %s" % config)
                    assert(os.path.exists(config));
                except:
                    try:
                        config = os.path.join(os.environ['HOME'], '.mtsendrc')
                        print("Looking for configuration file %s" % config)
                        assert(os.path.exists(config))
                    except:
                        config = 'mtsend.ini'
                        print("Looking for configuration file %s" % config)

        if os.access(config, os.R_OK):
            print("Using configuration file %s" % config)
        else:
            raise Exception('Configuration file doesn\'t exist or is not readable')

        return config

    def loadConfig(self, config):
        if config is None:
            config = self.getConfigFile()

        self.config = configparser.ConfigParser()
        self.config.read([config])

    def log(self, level, msg, *fmt):
        if self.verbose >= level:
            print(msg % fmt, file=sys.stderr)

    def setMode(self, mode, modeopt=None):
        if self.mode is None:
            self.mode = mode
            self.modeopt = modeopt
        else:
            raise Exception('Conflicting operational mode.')

    def _fixCategories(self, cts):
        if len(cts) > 0:
            srv = self.getRPCServer()
            new = []

            self.log(1, 'Retrieve available categories...')
            old = srv.mt.getCategoryList(self.get_blogid(), 
                self.get_username(), self.get_password())
            ctsmap = {}
            for cat in old:
                ctsmap[cat['categoryName'].lower()] = cat['categoryId']

            for cat in cts:
                try:
                    new.append({'categoryId': ctsmap[cat]})
                    del ctsmap[cat]
                except KeyError:
                    pass

            return new
        else:
            return []

    def _getBlog(self, option, default=None):
        if self.config is None:
            raise Exception('Configuration has not been loaded.')

        if self.alias is None:
            try:
                alias = self._getGlobal('default')
            except KeyError:
                raise Exception('Blog alias has not been specified.')
        else:
            alias = self.alias

        try:
            return self.config.get('blog-%s' % alias, option)
        except configparser.Error:
            if default is not None:
                return default
            else:
                raise KeyError(option)

    def _getGlobal(self, option, default=None):
        if self.config is None:
            raise Exception('Configuration has not been loaded.')
        try:
            return self.config.get('global', option)
        except configparser.Error:
            if default is not None:
                return default
            else:
                raise KeyError(option)

    def _getSite(self, option, default=None):
        try:
            if self.site is None:
                self.site = self._getBlog('site')

            return self.config.get('site-%s' % self.site, option)
        except (configparser.Error, KeyError):
            if default is not None:
                return default
            else:
                raise KeyError(option)


    class ProxyTransport(xmlrpc.client.Transport):
        """Transport class for the XMLRPC.

        Instead of using the HTTP/HTTPS transport, it tries to use a proxy
        server to send/receive XMLRPC messages. This transport must be
        initialised with the hostname and port number of the proxy server,
        e.g.

            transport = ProxyTransport('proxy.mydomain.com', 3128)
            server = Server("http://betty.userland.com", transport)
            print server.examples.getStateName(41)

        """

        def __init__(self, host, port=3128, username=None, password=None, 
                ssl=False):
            self.__host = host
            self.__port = port
            self.__username = username
            self.__password = password
            self.__ssl = ssl
            self.__target_host = None
            self._connection = (None, None)
            self._extra_headers = []
            self._use_builtin_types = True
            self._use_datetime = True
            self.user_agent = "Mozilla/5.0 (X11; %s %s) Firefox/%s mtsend.py/%s" % (platform.system(), platform.machine(), platform.python_version(),  __version__)


        def get_authentication(self):
            import base64
            auth_token = '%s:%s' % (self.__username, self.__password)
            auth_token = base64.encodestring(urllib.parse.unquote(auth_token))
            auth_token = auth_token.strip()
            return 'Basic '+auth_token


        def send_content(self, connection, request_body):
            """Send the content of the XML-RPC request to the server.

            This method override the default send_content. If the proxy
            username and password has been configured, then we will place an
            extra header here so the connection can be authenticated.

            """
            if (self.__username is not None) and (self.__password is not None):
                connection.putheader("Proxy-Authorization", 
                    self.get_authentication())

            xmlrpc.client.Transport.send_content(self, connection, request_body)


        def send_request(self, host, handler, request_body, debug):
            if not self.__ssl:
                prot = "http://"
            else:
                prot = "https://"

            handler = prot + host + handler
            return xmlrpc.client.Transport.send_request(self, self.__host, handler, request_body, debug)

        def make_connection(self, host):
            "Make a connection to the proxy server"

            # Note that we will try to connect to the proxy server instead of
            # our target host. It also needs to store the information about
            # the target host so that we can use that information in
            # send_request() call.

            return xmlrpc.client.Transport.make_connection(self, "%s:%d" % (host, self.__port))

def decode_iso8601(date):
    # Translate an ISO8601 date to the tuple format used in Python's time
    # module.
    regex = r'^(\d{4})-?(\d{2})-?(\d{2})[T\s](\d{2}):(\d{2}):(\d{2})'
    match = re.search(regex, str(date))
    if not match:
        raise Exception('"%s" is not a correct ISO8601 date format' % date)
    else:
        result = match.group(1, 2, 3, 4, 5, 6)
        result = list(map(int, result))
        result += [0, 1, -1]
        return tuple(result)


def get_rpc_transport(httptype):
    # Detect whether we need to use 'ProxyTranspory'. Proxy detection is
    # done using HTTP_PROXY or http_proxy environment variable.
    proxy = os.environ.get('HTTP_PROXY') or os.environ.get('http_proxy')
    if proxy:
        match = re.match(r'^(http://)?(([^:@]+)(:([^@]*))?@)?([^:]+):(\d+)',
            proxy)

        if match:
            username = match.group(3) or None
            password = match.group(5) or None
            hostname = match.group(6)
            bindport = int(match.group(7))

            return MTSend.ProxyTransport(hostname, bindport, username, password,
                httptype=='https')

    # Letting ServerProxy to pick the best suitable transport
    return None


re_date = r'^(\d{2})/(\d{2})/(\d{4}) (\d{2}):(\d{2}):(\d{2})( ([AP]M))?$'
re_date = re.compile(re_date).search

def parse_date(val):
    match = re_date(val.upper())
    if match is None:
        raise Exception('Date value "%s" is invalid.' % val)
    result = list(map(int, match.group(1, 2, 3, 4, 5, 6)))
    try:
        ampm = match.group(8)
    except IndexError:
        pass
    else:
        if ampm == 'PM':
            if result[3] != 12:
                result[3] += 12
        elif ampm == 'AM':
            if result[3] == 12:
                result[3] = 0
        elif ampm is not None:
            raise Exception('Expect (AM|PM) get "%s"' % ampm)

    result[0:3] = [result[2], result[0], result[1]]
    result += [0, 1, -1]

    return tuple(result)


def parse_post():
    state = 0
    code = None
    post = {}
    cts = []
    publish = xmlrpc.client.Boolean(0)

    for line in sys.stdin:
        line = line.rstrip()
        if state == 0:
            if line == '-----':
                state = 1
            else:
                idx = line.find(':')
                if idx < 0:
                    continue        # Invalid entry

                key, val = line[:idx].strip().upper(), line[idx+1:].strip()
                if key == 'TITLE':
                    post['title'] = val
                elif key == 'DATE':
                    val = time.strftime('%Y%m%dT%H:%M:%S', parse_date(val))
                    post['dateCreated'] = xmlrpc.client.DateTime(val)
                elif key == 'STATUS':
                    publish = xmlrpc.client.Boolean(val.lower() == 'publish')
                elif key == 'ALLOW COMMENTS':
                    val = int(val)
                    if val not in (0, 1, 2):
                        raise Exception('ALLOW COMMENTS must be either 0, 1 or 2')
                    post['mt_allow_comments'] = val
                elif key == 'ALLOW PINGS':
                    post['mt_allow_pings'] = int(val)
                elif key == 'PING':
                    try:
                        post['mt_tb_ping_urls'].append(val)
                    except KeyError:
                        post['mt_tb_ping_urls'] = [val]
                elif key == 'CONVERT BREAKS':
                    # MT2.6 - mt_convert_breaks has changed its value from
                    # XML-RPC boolean to string.
                    post['mt_convert_breaks'] = val
                elif key == 'POSTID':
                    post['postid'] = val
                elif key == 'PRIMARY CATEGORY':
                    cts.insert(0, val.lower())
                elif key == 'CATEGORY':
                    cts.append(val.lower())
                elif key == 'KEYWORDS':
                    post['mt_keywords'] = val
                else:
                    raise Exception('Invalid field key: %s' % key)

        elif state == 1:
            line = line.upper()
            if line == 'BODY:':
                code = 'description'
            elif line == 'EXTENDED BODY:':
                code = 'mt_text_more'
            elif line == 'EXCERPT:':
                code = 'mt_excerpt'
            else:
                raise Exception('Invalid line in the current state: %s' % line)

            state = 2

        elif state == 2:
            if line.startswith('-----') and (not line.rstrip('-')):
                code = None
                state = 1
            else:
                if code in post:
                    post[code] += '\n' + line
                else:
                    post[code]  = line


    return post, cts, publish


def print_post(post, cts):
    if 'title' in post:
        print('TITLE:', post['title'])
    print('DATE:', time.strftime('%m/%d/%Y %H:%M:%S',
        decode_iso8601(post['dateCreated'])))

    for cat in cts:
        if cat['isPrimary']:
            print('PRIMARY CATEGORY:', cat['categoryName'])
        print('CATEGORY:', cat['categoryName'])

    if 'post_status' in post:
        print('STATUS: ', post['post_status'])
    else:
        # We cannot really determine whether the post has been published.
        # Therefore we assume that it is.
        print('STATUS: publish')

    if 'mt_allow_comments' in post:
        print('ALLOW COMMENTS:', post['mt_allow_comments'])

    if 'mt_allow_pings' in post:
        print('ALLOW PINGS:', post['mt_allow_pings'])

    if 'mt_convert_breaks' in post:
        print('CONVERT BREAKS:', post['mt_convert_breaks'])

    if post.get('mt_keywords'):
        print('KEYWORDS:', post['mt_keywords'])

    # We will also print the postid so that it can be verified later.
    print('POSTID:', post['postid'])

    # Start printing the body
    if post.get('description'):
        print('-----')
        print('BODY:')
        print(post['description'])

    if post.get('mt_text_more'):
        print('-----')
        print('EXTENDED BODY:')
        print(post['mt_text_more'])

    if post.get('mt_excerpt'):
        print('-----')
        print('EXCERPT:')
        print(post['mt_excerpt'])


def print_table(table):
    # We have to work out the maximum width first.
    if not table:
        return

    widths = [0] * len(table[0])
    for row in table:
        for idx, cell in zip(list(range(len(row))), row):
            cell = str(cell)
            row[idx] = cell
            if len(cell) > widths[idx]:
                widths[idx] = len(cell)

    border = '+'+('+'.join(['-'*(width + 2) for width in widths]))+'+'
    format = '|'+('|'.join([' %% %ds ' % width for width in widths]))+'|'

    hdrs = 0

    print(border)
    for row in table:
        print(format % tuple(row))
        if (not hdrs) and (len(table) > 1):
            print(border)
            hdrs = 1
    print(border)


def main(args):
    import getopt
    try:
        opts, args = getopt.getopt(args, 'A:a:B:Cc:D:E:G:hL:NP:qR:TU:vVX:')
    except getopt.GetoptError as ex:
        print('Error: '+str(ex), file=sys.stderr)
        print(__doc__, file=sys.stderr)
        sys.exit(1)

    mtsend = MTSend()
    config = None

    for opt, arg in opts:
        if opt == '-A':
            mtsend.setMode('a', arg)
        elif opt == '-a':
            mtsend.alias = arg
        elif opt == '-B':
            mtsend.setMode('b', arg)
        elif opt == '-C':
            mtsend.setMode('c')
        elif opt == '-c':
            if os.access(arg, os.R_OK):
                config = arg
            else:
                print(mtsend.getConfigFile(), file=sys.stderr)
                sys.exit(0)
        elif opt == '-D':
            mtsend.setMode('d', arg)
        elif opt == '-E':
            mtsend.setMode('e', arg)
        elif opt == '-G':
            mtsend.setMode('g', arg)
        elif opt == '-h':
            print(__doc__, file=sys.stderr)
            sys.exit(0)
        elif opt == '-L':
            mtsend.setMode('l', arg)
        elif opt == '-N':
            mtsend.setMode('n')
        elif opt == '-P':
            mtsend.setMode('p', arg)
        elif opt == '-q':
            mtsend.verbose -= 1
        elif opt == '-R':
            mtsend.setMode('r', arg)
        elif opt == '-T':
            mtsend.setMode('t')
        elif opt == '-U':
            mtsend.setMode('u', arg)
        elif opt == '-v':
            mtsend.verbose += 1
        elif opt == '-V':
            print('Version %s' % __version__, file=sys.stderr)
            sys.exit(0)
        elif opt == '-X':
            mtsend.setMode('x', arg)
        else:
            print('Warning: Option "%s" is not handled.' % opt, file=sys.stderr)

    if mtsend.mode is None:
        print('Error: Action is not specified', file=sys.stderr)
        print(__doc__, file=sys.stderr)
        sys.exit(1)

    try:
        mtsend.loadConfig(config)
        mtsend.execute()
    except Exception as ex:
        if mtsend.verbose > 1:
            raise
        else:
            print('Error:', ex, file=sys.stderr)


if __name__ == '__main__':
    main(sys.argv[1:])
