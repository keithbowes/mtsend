#!/usr/bin/env python

'''\
Usage: 
    mtsend.py [action] [options]

Actions:
    -B site     List all the blogs you can access in [site]. Site has to be in
                the configuration file.
    -C          Print out a list of existing categories.
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
    -R postid   Rebuild all the static files related to this entry.
    -U filename Upload a file, reading from standard input, to the blog site,
                with destination filename provided. (MT>=2.6)
    -V          Show version information.

Options:
    -a alias    Use "alias" as the blog alias. This script will locate
                relavent site URL/username/password information using this
                alias.
    -c config   Load "config" as configuration file, instead of $HOME/.mtsendrc
    -h          Display this help message.
    -q          Decrease verbose level.
    -v          Increase verbose level. Message goes to standard error.
'''

xtra_help = '''\
Configuration File:
    Default configuration file is located at $HOME/.mtsendrc, and it is in the
    similar format of typical Windows INI files. Here is a sample option file:

        [global]
        default=mysite

        [site-mysite]
        url=http://myhost.mydomain/mt/mt-xmlrpc.cgi
        username=myusername
        password=mypassword
        mtversion=2.6.3

        [blog-myblog]
        site=mysite
        blogid=3

        [blog-anotherblog]
        site=mysite
        blogid=4

    In this configuration, two blog aliases have been defined - "myblog" and
    "anotherblog". Both blogs use site configuration "mysite", where this
    script can find corresponding URL/username/password. In the "global"
    section, it defines the default blog alias, which will be used when -a
    command line option is not used.

Input/Ouput File Format
    The input file for -N and -E action is in the same format as the output
    file with -G action. Therefore, you can use -G to retrieve the blog entry,
    edit it, and then use "-E -" to save the entry back to Movable Type.

    The file type is very similar to Movable Type's import/export file format,
    except that you can only have one blog entry per file. Moreover, you
    cannot have traceback/comment in the input/output file, as they are not
    supported by the MT's XML-RPC interface. For more information, check the
    Movable Type Import Format document:

        http://www.movabletype.org/docs/mtimport.html

'''

__author__  = 'Scott Yang'
__version__ = 'Version 0.4'

import ConfigParser
import os
import sys
import time

class MT:
    def __init__(self):
        self.alias = None
        self.input = None
        self.config = None
        self.mode = None
        self.verbose = 1


    def __getattr__(self, attr):
        if attr == 'blogid':
            return self._getBlog('blogid')
        elif attr == 'mtversion':
            # Try to find out the MovableType version of the site. In the
            # configuration file, under the site sections, "mtversion" option
            # can be specified. If it does not exist, then it will assume the
            # site is MovableType 2.5.x (which might be the minimum supported
            # by mtsend.py
            import re
            mtversion = self._getSite('mtversion', '2.5')
            mtversion = re.match(r'^\d+\.\d+', mtversion)
            if mtversion:
                return float(mtversion.group(0))
            else:
                return 2.5
        elif attr == 'password':
            return self._getSite('password')
        elif attr == 'username':
            return self._getSite('username')
        else:
            raise AttributeError, attr

    def execute(self):
        try:
            handler = getattr(self, 'execute_%s' % self.mode)
        except AttributeError:
            raise Exception, 'Unknown execution mode: %s' % self.mode
        else:
            handler()

    def execute_b(self):
        self.site = self.modeopt
        srv = self.getRPCServer()
        blogs = srv.blogger.getUsersBlogs('', self.username, self.password)
        result = [['ID', 'Blog Name', 'URL']]
        for b in blogs:
            result.append([b['blogid'], b['blogName'], b['url']])
        printTable(result)

    def execute_c(self):
        srv = self.getRPCServer()
        cts = srv.mt.getCategoryList(self.blogid, self.username, self.password)
        result = [['ID', 'Category Name']]
        for cat in cts:
            result.append([cat['categoryId'], cat['categoryName']])
        printTable(result)

    def execute_e(self):
        self.log(1, 'Parsing post entry from standard input...')
        post, cts, publish = parsePost(self.mtversion)

        postid = self.modeopt
        if self.modeopt == '-':
            try:
                postid = post['postid']
            except KeyError:
                raise Exception, 'Cannot discover post ID from the input.'
            
        elif post.has_key('postid') and (post['postid'] != postid):
            raise Exception, \
                'Post ID does not match. ID in the input is "%s"' % \
                    post['postid']

        srv = self.getRPCServer()
        self.log(1, 'Saving post entry "%s"...', postid)
        srv.metaWeblog.editPost(postid, self.username, 
                                self.password, post, publish)

        cts = self._fixCategories(cts)
        if len(cts) > 0:
            self.log(1, 'Add categories "%s" to post entry "%s"...',
                     ','.join([x['categoryId'] for x in cts]), postid)
            srv.mt.setPostCategories(postid, self.username, self.password, cts)
 
    def execute_g(self):
        srv = self.getRPCServer()
        if self.modeopt.lower() == '-':
            self.log(1, 'Retrieve most recent post entry...')
            post = srv.metaWeblog.getRecentPosts\
                ( self.blogid, self.username, self.password, 1 )
            if len(post) > 0:
                post = post[0]
            else:
                raise Exception, 'The current blog does not have any entry.'
        else:
            self.log(1, 'Retrieve post entry "%s"...', self.modeopt)
            post = srv.metaWeblog.getPost\
                ( self.modeopt, self.username, self.password )

        # Get the categories of this post.
        self.log(1, 'Retrieve categories for post entry "%s"...', 
                 post['postid'])
        cts = srv.mt.getPostCategories\
            ( post['postid'], self.username, self.password )

        printPost(post, cts)

    def execute_l(self):
        srv = self.getRPCServer()
        try:
            num = int(self.modeopt)
        except:
            num = 5

        # For MT2.6, a bandwidth-saving version "mt.getRecentPostTitles()"
        # should be used. However, we should still keep the compatibility with
        # MT2.5 by checking the version setting.
        if self.mtversion >= 2.6:
            func = srv.mt.getRecentPostTitles
        else:
            func = srv.mt.getRecentPosts

        posts = func(self.blogid, self.username, self.password, num)

        self.log(1, 'Retrieve "%d" recent posts...', num)
        result = [['ID', 'Date', 'Title']]
        for p in posts:
            result.append([
                p['postid'],
                time.strftime('%Y-%m-%d %H:%M:%S', 
                              decodeISO8601(p['dateCreated'].value)),
                p['title']
            ])

        printTable(result)

    def execute_n(self):
        self.log(1, 'Parsing post entry from standard input...')
        post, cts, publish = parsePost(self.mtversion)
        srv = self.getRPCServer()

        self.log(1, 'Saving new post entry...')
        postid = srv.metaWeblog.newPost(self.blogid, self.username, 
                                        self.password, post, publish)

        cts = self._fixCategories(cts)
        if len(cts) > 0:
            self.log(1, 'Add categories "%s" to post entry "%s"...',
                     ','.join([x['categoryId'] for x in cts]), postid)
            srv.mt.setPostCategories(postid, self.username, self.password, cts)

        # Somehow under MovableType 2.5, the new post will not trigger a
        # rebuild. Therefore we will force a rebuild here.
        self.modeopt = postid
        self.execute_r()

        print postid
    
    def execute_r(self):
        srv = self.getRPCServer()
        self.log(1, 'Rebuild post entry "%s"...', self.modeopt)
        srv.mt.publishPost(self.modeopt, self.username, self.password)

    def execute_u(self):
        if self.mtversion < 2.6:
            raise Exception, \
                'File uploading requires MovableType 2.6+ on the server side.'
        
        srv = self.getRPCServer()
        bin = sys.stdin.read()

        self.log(1, 'Uploading "%s" (%d bytes)...', self.modeopt, len(bin))
        media_object = {
            'name': self.modeopt,
            'bits': xmlrpclib.Binary(bin),
        }
        
        result = srv.metaWeblog.newMediaObject(self.blogid, self.username, 
                                               self.password, media_object)

        print result['url']


    def getRPCServer(self):
        return xmlrpclib.Server(self._getSite('url'))

    def loadConfig(self, config):
        if config is None:
            config = os.path.join(os.environ['HOME'], '.mtsendrc')

        if not os.access(config, os.R_OK):
            raise Exception, \
                'Configuration file "%s" is not readable' % config
            
        self.config = ConfigParser.ConfigParser()
        self.config.read([config])

    def log(self, level, msg, *fmt):
        if self.verbose >= level:
            print >>sys.stderr, msg % fmt

    def setMode(self, mode, modeopt=None):
        if self.mode is None:
            self.mode = mode
            self.modeopt = modeopt
        else:
            raise Exception, 'Conflicting operational mode.'

    def _fixCategories(self, cts):
        if len(cts) > 0:
            srv = self.getRPCServer()
            new = []

            self.log(1, 'Retrieve available categories...')
            old = srv.mt.getCategoryList(self.blogid, self.username, 
                                         self.password)
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
            raise Exception, 'Configuration has not been loaded.'

        if self.alias is None:
            try:
                alias = self._getGlobal('default')
            except KeyError:
                raise Exception, 'Blog alias has not been specified.'
        else:
            alias = self.alias

        try:
            return self.config.get('blog-%s' % alias, option)
        except ConfigParser.Error:
            if default is not None:
                return default
            else:
                raise KeyError, option

    def _getGlobal(self, option, default=None):
        if self.config is None:
            raise Exception, 'Configuration has not been loaded.'
        try:
            return self.config.get('global', option)
        except ConfigParser.Error:
            if default is not None:
                return default
            else:
                raise KeyError, option

    def _getSite(self, option, default=None):
        try:
            try:
                site = self.site
            except AttributeError:
                site = self._getBlog('site')
                self.site = site
                
            return self.config.get('site-%s' % site, option)
        except (ConfigParser.Error, KeyError):
            if default is not None:
                return default
            else:
                raise KeyError, option

    def _readInputFromEditor(self):
        # Figure out which editor should we run. We will look at the EDITOR
        # environment variable first.
        try:
            editor = os.environ['EDITOR']
        except KeyError:
            raise Exception, 'Environment variable "EDITOR" is not set.'
        

def decodeISO8601(date):
    # Translate an ISO8601 date to the tuple format used in Python's time
    # module.
    import re
    regex = r'^(\d{4})(\d{2})(\d{2})T(\d{2}):(\d{2}):(\d{2})$'
    match = re.search(regex, str(date))
    if not match:
        raise Exception, '"%s" is not a correct ISO8601 date format' % date
    else:
        result = match.group(1, 2, 3, 4, 5, 6)
        result = map(int, result)
        result += [0, 0, -1]
        return tuple(result)


def parseBoolean(mtversion, value):
    # In the MovableType 2.5.x XML-RPC specification, boolean values are real
    # XML-RPC boolean objects. Whereas in MovableType 2.6.x, it changes to
    # simple integer values.
    if mtversion >= 2.6:
        return value == '1' and 1 or 0
    else:
        return xmlrpclib.Boolean(value == '1')

    
def parsePost(mtversion=2.5):
    state = 0
    code = None
    post = {}
    post['dateCreated'] = xmlrpclib.DateTime(time.strftime('%Y%m%dT%H:%M:%S'))
    cts = []
    publish = xmlrpclib.Boolean(0)

    while 1:
        line = sys.stdin.readline()
        if line == '':
            break

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
                    import re
                    regex = r'^(\d{2})/(\d{2})/(\d{4}) (\d{2}):(\d{2}):(\d{2})( ([AP]M))?$'
                    match = re.search(regex, val.upper())
                    if match is None:
                        raise Exception, 'Date value "%s" is invalid.' % val
                    result = map(int, match.group(1, 2, 3, 4, 5, 6))
                    try:
                        pm = match.group(8) == 'PM'
                    except IndexError:
                        pass
                    else:
                        if match.group(8) == 'PM':
                            if result[3] != 12:
                                result[3] += 12
                        elif result[3] == 12:
                            result[3] = 0

                    result[0:3] = [result[2], result[0], result[1]]
                    result += [0, 0, -1]
                        
                    val = time.strftime('%Y%m%dT%H:%M:%S', tuple(result))
                    post['dateCreated'] = xmlrpclib.DateTime(val)
                    
                elif key == 'STATUS':
                    publish = xmlrpclib.Boolean(val.lower() == 'publish')

                elif key == 'ALLOW COMMENTS':
                    post['mt_allow_comments'] = parseBoolean(mtversion, val)
        
                elif key == 'ALLOW PINGS':
                    post['mt_allow_pings'] = parseBoolean(mtversion, val)

                elif key == 'CONVERT BREAKS':
                    # MT2.6 - mt_convert_breaks has changed its value from
                    # XML-RPC boolean to string. Probably in preparation of
                    # supporting multiple transformattion backend.
                    if mtversion < 2.6:
                        val = xmlrpclib.Boolean(val == '1')
                    else:
                        val = (val == '1') and '1' or '0'
                    
                    post['mt_convert_breaks'] = val
 
                elif key == 'POSTID':
                    post['postid'] = val
 
                elif key == 'PRIMARY CATEGORY':
                    cts.insert(0, val.lower())

                elif key == 'CATEGORY':
                    cts.append(val.lower())

                else:
                    raise Exception, 'Invalid field key: %s' % key

        elif state == 1:
            line = line.upper()
            if line == 'BODY:':
                code = 'description'
            elif line == 'EXTENDED BODY:':
                code = 'mt_text_more'
            elif line == 'EXCERPT:':
                code = 'mt_excerpt'
            else:
                raise Exception, 'Invalid line in the current state: %s' % line

            state = 2

        elif state == 2:
            if line == '-----':
                code = None
                state = 1
            else:
                if post.has_key(code):
                    post[code] += '\n' + line
                else:
                    post[code]  = line


    return post, cts, publish


def printBoolean(val):
    if isinstance(val, xmlrpclib.Boolean):
        return val and '1' or '0'
    elif type(val) == type(1):
        return val and '1' or '0'
    elif type(val) == type('1'):
        return val == '1' and '1' or '0'

    assert(0), 'Invalid boolean value: %s' % val


def printPost(post, cts):
    if post.has_key('title'):
        print 'TITLE:', post['title']
    print 'DATE:', \
        time.strftime('%m/%d/%Y %H:%M:%S',
                      decodeISO8601(post['dateCreated'].value))
                      
    for cat in cts:
        if cat['isPrimary']:
            print 'PRIMARY CATEGORY:', cat['categoryName']
        print 'CATEGORY:', cat['categoryName']

    # We cannot really determine whether the post has been published.
    # Therefore we assume that it is.
    print 'STATUS: publish'

    if post.has_key('mt_allow_comments'):
        print 'ALLOW COMMENTS:', printBoolean(post['mt_allow_comments'])
    
    if post.has_key('mt_allow_pings'):
        print 'ALLOW PINGS:', printBoolean(post['mt_allow_pings'])
    
    if post.has_key('mt_convert_breaks'):
        # MT2.6 - mt_convert_breaks has changed its value from XML-RPC boolean
        # to string. Probably in preparation of supporting multiple
        # transformattion backend.
        val = post['mt_convert_breaks']
        if isinstance(val, xmlrpclib.Boolean):
            val = val and '1' or '0'

        print 'CONVERT BREAKS:', val

    # We will also print the postid so that it can be verified later.
    print 'POSTID:', post['postid']

    # Start printing the body
    if post.has_key('description') and post['description']:
        print '-----'
        print 'BODY:'
        print post['description']

    if post.has_key('mt_text_more') and post['mt_text_more']:
        print '-----'
        print 'EXTENDED BODY:'
        print post['mt_text_more']
        
    if post.has_key('mt_excerpt') and post['mt_excerpt']:
        print '-----'
        print 'EXCERPT:'
        print post['mt_excerpt']


def printTable(table, heading=1):
    # We have to work out the maximum width first.
    if not table:
        return

    widths = [0] * len(table[0])
    for row in table:
        for idx, cell in zip(range(len(row)), row):
            if len(cell) > widths[idx]:
                widths[idx] = len(cell)

    border = '+'+('+'.join(['-'*(w+2) for w in widths]))+'+'
    format = '|'+('|'.join([' %%-%ds ' % w for w in widths]))+'|'

    hdrs = 0

    print border
    for row in table:
        print format % tuple(row)
        if (not hdrs) and heading and (len(table) > 1):
            print border
            hdrs = 1
    print border


def main(args):
    import getopt
    import socket
    try:
        opts, args = getopt.getopt(args, 'a:B:Cc:E:G:hL:NqR:U:vV')
    except getopt.GetoptError, ex:
        print >>sys.stderr, 'Error: '+str(ex)
	print >>sys.stderr, __doc__
	sys.exit(1)

    mt = MT()
    config = None

    for o, a in opts:
        if o == '-a':
            mt.alias = a
        elif o == '-B':
            mt.setMode('b', a)
        elif o == '-C':
            mt.setMode('c')
        elif o == '-c':
            config = a
        elif o == '-E':
            mt.setMode('e', a)
        elif o == '-G':
            mt.setMode('g', a)
        elif o == '-h':
            print >>sys.stderr, __doc__
            print >>sys.stderr, xtra_help
            sys.exit(0)
        elif o == '-L':
            mt.setMode('l', a)
        elif o == '-N':
            mt.setMode('n')
        elif o == '-q':
            mt.verbose -= 1
        elif o == '-R':
            mt.setMode('r', a)
        elif o == '-U':
            mt.setMode('u', a)
        elif o == '-v':
            mt.verbose += 1
        elif o == '-V':
            print >>sys.stderr, __version__
            sys.exit(0)
        else:
            print >>sys.stderr, 'Warning: Option "%s" is not handled.' % o

    if mt.mode is None:
        print >>sys.stderr, 'Error: Action is not specified'
        print >>sys.stderr, __doc__
        sys.exit(1)

    try:
        global xmlrpclib
        import xmlrpclib
    except ImportError:
        print >>sys.stderr, '''Error: Cannot import "xmlrpclib" module.

You should either upgrade to Python 2.2+, or download and install the 
"xmlrpclib" from the following website:

    http://www.pythonware.com/products/xmlrpc/
'''
        sys.exit(1)

    try:
        mt.loadConfig(config)
        mt.execute()
    except Exception, ex:
        if mt.verbose > 1:
            raise
        else:
            print >>sys.stderr, 'Error:', ex


if __name__ == '__main__':
    main(sys.argv[1:])
