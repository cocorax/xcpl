# *****************************************************************************
# *****************************************************************************
#
#		Name:		xparser.py
#		Purpose:	XCPL Parser
#		Date: 		6th June 2020
#		Author:		Paul Robson (paul@robsons.org.uk)
#
# *****************************************************************************
# *****************************************************************************

from error import *
import traceback

# *****************************************************************************
#
#							Parses a text file
#
# *****************************************************************************

class TextParser(object):
	def __init__(self,text):
		text = [x if x.find("#") < 0 else x[:x.find("#")] for x in text]	# Remove comments
		text = [x.replace("\t"," ").strip() for x in text]					# Remove tabs and strip
		self.src = (" "+TextParser.LINEMARKER).join(text)					# Make one long string
		self.macroDepth = 0
		self.current = 0
		self.charStack = ""
		self.tokenStack = []
		XCPLException.LINE = 1
		self.doublePunct = { ">=":0,"<=":0,"<>":0,"==":0,"<<":0,">>":0,"++":0,"--":0  }	# Two char punc tokens.
	#
	#		Get a character from the stream
	#
	def getChar(self):
		while self.src.startswith(TextParser.LINEMARKER):					# Process markers
			self.src = self.src[1:]
			XCPLException.LINE += 1
		if self.src == "":													# Nothing left.
			return ""
		ch = self.src[0] 													# Char to return
		self.src = self.src[1:]
		return ch
	#
	#		Return a character to the stream
	#
	def putChar(self,ch):
		self.src = ch + self.src
	#
	#		Extract one element. This is a constant (in decimal), a string (prefixed with ")
	#		an alphanumeric identifier, or a punctuation element.
	#
	def get(self):
		if len(self.tokenStack) > 0:										# Something on the stack
			return self.tokenStack.pop()
		#
		ch = self.getChar()													# Get character
		if ch == "":														# Nothing left.
			return ch 														
		if ch == " ":														# Skip spaces
			return self.get()
		#
		#		Constants (all map to decimal integer) including '<char>' and $hex
		#
		if ch >= '0' and ch <= '9':											# constant (decimal)
			return self.extract(ch,TextParser.DIGITS)
		if ch == '$':														# constant (hexadecimal)
			s = self.extract("",TextParser.HEXDIGITS)
			if s == "":
				raise XCPLException("Badly formed hexadecimal constant")
			return str(int(s,16))											
		if ch == "'":														# character
			c1 = self.getChar()												# get next two
			c2 = self.getChar()
			if c2 != "'":													# check 'x'
				raise XCPLException("Badly formed character constant")
			return str(ord(c1))
		#
		#		Quoted string (map to string prefixed by ")
		#
		if ch == '"':														# Quoted string.
			s = ""
			ch = self.getChar()														
			while ch != "" and ch != '"':									# Go till end or "
				s = s + ch
				ch = self.getChar()
			if ch == "":													# No closing quote
				raise XCPLException("No closing quote")
			return '"'+s 
		#
		#		Alphanumeric identiifer
		#
		if TextParser.ALPHA.find(ch.upper()) >= 0:							# Identifier.
			ident = self.extract(ch,TextParser.IDENTCHAR).lower()			# get identifier
			if ident == "define":											# macro definition
				self.defineMacro()											# do that definition
				ident = self.get()											# and get the nex item
			if ident in TextParser.Macros:									# is it a macro ?
				self.macroDepth += 1										# we track too much recursion
				if self.macroDepth == 5:									# and this is too much recursion
					raise XCPLException("Define macros too deep")
				self.src = TextParser.Macros[ident]+" "+self.src			# put into the source
				self.macroDepth -= 1
				ident = self.get()											# and get it.
			return ident
		#
		#		One or two character punctuation mix.
		#
		c2 = self.getChar()													# Get next one
		if ch+c2 in self.doublePunct:										# Check for 2 char punc.
			return ch+c2
		self.putChar(c2)
		return ch
	#
	#		Extract a sequence that contains the included characters
	#
	def extract(self,s,allowed):
		ch = self.getChar().upper() 										# check next
		while ch != "" and allowed.find(ch) >= 0:							# keep going while found
			s = s + ch
			ch = self.getChar().upper()
		if ch != "":														# put back one that didn't match
			self.putChar(ch)
		return s
	#
	#		Handle macro definition
	#
	def defineMacro(self):
		name = self.get()													# get name must be identifier
		body = self.get()													# get body must be quoted string
		if TextParser.ALPHA.find(name[0].upper()) < 0 or body[0] != '"':	# check syntax
			raise XCPLException("Bad macro syntax")
		if name in TextParser.Macros and TextParser.Macros[name] != body:	# check redefinition
			raise XCPLException("Macro "+name+" redefined")
		TextParser.Macros[name] = body[1:] 									# save macro
	#
	#		Put one element back
	#
	def put(self,element):
		self.tokenStack.append(element)

TextParser.LINEMARKER = chr(128)											# used to mark line ends.
TextParser.DIGITS = "0123456789"											# token match lists.
TextParser.HEXDIGITS = TextParser.DIGITS+"ABCDEF"
TextParser.ALPHA = "ABDCDEFGHIJKLMNOPQRSTUVWXYZ"
TextParser.ALPHANUM = TextParser.ALPHA+TextParser.DIGITS
TextParser.IDENTCHAR = TextParser.ALPHANUM+"_."

TextParser.Macros = {  }													# macro store.

if __name__ == "__main__":
	s = """
#	Hello world
define text "chips in gravy"
432 $4A3 '*' "hello, world"
this is a00 >>=<4
text element		# with a comment
""".split("\n")
	tp = TextParser(s)
	c = tp.get()
	while c != "":
		print(XCPLException.LINE,c)
		c = tp.get()
