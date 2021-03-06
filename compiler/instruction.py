# *****************************************************************************
# *****************************************************************************
#
#		Name:		Instruction.py
#		Purpose:	Instruction compiler
#		Date: 		8th June 2020
#		Author:		Paul Robson (paul@robsons.org.uk)
#
# *****************************************************************************
# *****************************************************************************

from error import *
from xparser import *
from ident import *
from codegen import *
from x16codegen import *
from xtypes import *
from term import *
from expression import *

# *****************************************************************************
#
#						Instruction compiler worker class
#
# *****************************************************************************

class InstructionCompiler(object):
	def __init__(self,codeGenerator,identStore):
		assert codeGenerator is not None
		self.cg = codeGenerator													# save code generator
		self.ident = identStore													# save ident store
		self.termCompiler = TermCompiler(self.cg,self.ident)					# Create term/expression compiler
		self.exprCompiler = ExpressionCompiler(self.cg,self.ident)				# workers.
		for k in Sour16.ROUTINES.keys():										# copy routines in.
			self.defineProcedure(k[:-1],Sour16.ROUTINES[k],int(k[-1]))
	#
	#		Define a procedure
	#
	def defineProcedure(self,name,addr,paramCount):			
		self.ident.set(True,name,addr)											# as globals.
		self.ident.setAssoc(addr,paramCount)									# save parameter count
	#
	#		Compile one Instruction
	#
	def compile(self,stream):
		s = stream.get()														# get next token.
		if s == "":																# check something.
			return False
		elif s == "{":															# code group.
			self.compileBlock(stream)
		elif s == "var":														# Variable declaration
			self.compileVariableDeclaration(stream,False)
		elif s == "if":															# Condition.
			self.compileIf(stream)
		elif s == "repeat":														# Loops
			self.compileRepeat(stream)
		elif s == "while":
			self.compileWhile(stream)
		elif s == "do":															
			self.compileDo(stream)		
		else:																	# don't recognise it.
			stream.put(s)														# put it back
			self.compileIdentifier(stream)										# assume it's an identifier.
		return True
	#
	#		Compile a block.
	#
	def compileBlock(self,stream):
		cmd = stream.get()
		while cmd != "}":
			stream.put(cmd)
			self.compile(stream)
			cmd = stream.get()
	#
	#		Compile a variable declaration.
	#
	def compileVariableDeclaration(self,stream,isGlobal):
		cont = ","
		while cont == ",":														# keep going while more
			ident = stream.get()												# new name
			if not self.isIdentifier(ident):
				raise XCPLException("Missing variable name")
			cont = stream.get()													# what follows
			if cont == "[":														# uninitialised data ?
				size = self.termCompiler.compile(stream,0,self.exprCompiler)	# get amount
				if size[0] != VType.CONST or size[1] == 0:						# bad array size
					raise XCPLException("Bad array size")
				self.checkNext(stream,"]")
				cont = stream.get()
				array = self.cg.allocUninitialised(size[1])						# allocate memory
				addr = self.cg.writeDataMemory(array & 0xFF) 					# create reference to it
				self.cg.writeDataMemory(array >> 8)
			else:
				addr = self.cg.allocUninitialised(2)							# just a word
			self.ident.set(isGlobal,ident,addr)									# define it.
		#
		if cont != ";":															# must end with ;
			raise XCPLException("Missing ; on variable definition")
	#
	#		Compile an if / else command
	#
	def compileIf(self,stream):
		self.exprCompiler.compileValue(stream,1,self.termCompiler)				# test
		branchAddr = self.compileBranch("Z")									# compile branch if failed.
		self.compile(stream);													# body
		s = stream.get()														# check for else ?
		if s == "else":
			newBranch = self.compileBranch()									# branch out after if clause
			self.patchBranch(branchAddr,self.getAddress())						# fix up if IF failed.
			self.compile(stream)												# else body
			self.patchBranch(newBranch,self.getAddress())						# branch to skip else code
		else:																		
			stream.put(s)														# no else, put it back	
			self.patchBranch(branchAddr,self.getAddress())						# complete the branch
	#
	#		Compile a repeat loop
	#
	def compileRepeat(self,stream):
		loopAddr = self.getAddress()											# get loop address.
		self.compile(stream)													# check the block
		self.checkNext(stream,"until")											# check for until
		self.exprCompiler.compileValue(stream,1,self.termCompiler)				# test
		branchAddr = self.compileBranch("Z")									# compile branch.
		self.patchBranch(branchAddr,loopAddr)									# fix up branch.
		self.checkNext(stream,";")
	#
	#		Compile a while loop
	#
	def compileWhile(self,stream):
		loopAddr = self.getAddress()											# get loop address.
		self.exprCompiler.compileValue(stream,1,self.termCompiler)				# test
		branchAddr = self.compileBranch("Z")									# compile branch out.
		self.compile(stream)													# check the block
		loopBackAddr = self.compileBranch() 									# loop back to before test.
		self.patchBranch(loopBackAddr,loopAddr)
		self.patchBranch(branchAddr,self.getAddress())							# fix up branch after test
	#
	#		Compile a do loop
	#
	def compileDo(self,stream):
		self.checkNext(stream,"(")												# must have a bracket
		self.exprCompiler.compileValue(stream,1,self.termCompiler)				# the loop count into R1
		s = stream.get()														# what follows ?
		if s == ",":															# user provided variable
			s = self.termCompiler.compile(stream,0,self)						# get that variable
			if s[0] != VType.VARREF:
				raise XCPLException("Do loop index must be a variable")
			addr = s[1]															# index address.
			self.checkNext(stream,")")											# check closing bracket
		elif s == ")":															# automatic variable
			addr = self.cg.allocUninitialised(2)								# so get space for it
		else:
			raise XCPLException("Syntax Error")
		self.termCompiler.loadConstantCode(0,addr)								# save initial index value.
		self.cg.c_sia(1)														# store it
		doLoop = self.getAddress()												# top of loop
		self.termCompiler.loadConstantCode(1,addr)								# decrement count at top of loop
		self.cg.c_call(Sour16.X_DECLOAD)
		self.compile(stream)													# loop body.
		self.cg.c_ldr(1,addr)													# load loop counter into R1
		branchCode = self.compileBranch("NZ")									# branch back if non zero
		self.patchBranch(branchCode,doLoop)
	#
	#		Compile when an identifier is the first element. Can be an assignment, procedure call.
	#	
	def compileIdentifier(self,stream):
		r = self.exprCompiler.compile(stream,0,self.termCompiler)				# compile the address as l-expr
		s = stream.get()														# what follows ?
		#
		#		Handle assignment
		#
		if s == "=":
			if r[0] == VType.VARREF:											# variable reference.
				self.termCompiler.loadConstantCode(0,r[1])						# load variable addr -> R0
				r = [VType.WORDREF] 											# it's now a word reference.
			self.exprCompiler.compileValue(stream,1,self.termCompiler) 			# do the right hand side -> R1
			if r[0] == VType.WORDREF:
				self.cg.c_sia(1) 												# save word indirect 												
			else:
				self.cg.c_sbi(1)												# save byte indirect
			self.checkNext(stream,";")
		#
		#		Auto increment/decrement variable.
		#
		elif s == "++" or s == "--":
			if r[0] != VType.VARREF:											# variable reference.
				raise XCPLException("++/-- must be applied to variables")
			self.termCompiler.loadConstantCode(1,r[1])							# address to R1
			if s == "++":														# call appropriate function.
				self.cg.c_call(Sour16.X_INCLOAD)
			else:
				self.cg.c_call(Sour16.X_DECLOAD)
			self.checkNext(stream,";")
		#
		#		Procedure invocation. Params are stored in r1,r2,r3,r4 etc.
		#
		elif s == "(":	
			paramCount = 0														# how many parameters
			s = stream.get()													# see if ) follows
			if s != ")":
				stream.put(s)													# if not, put it back
				nextToken = ","
				while nextToken == ",":											# keep going while more
					paramCount += 1												# bump count and get params
					self.exprCompiler.compileValue(stream,paramCount,self.termCompiler)	
					nextToken = stream.get()									# see what is next.
				if nextToken != ")":											# check final )
					raise XCPLException("Missing ) from procedure call")
			self.cg.c_call(r[1])												# generate call
			pCount = self.ident.getAssoc(r[1])									# get associated value
			if pCount is not None:												# if we know the # of params
				if paramCount != pCount:										# check it
					raise XCPLException("Parameter count mismatch")
			self.checkNext(stream,";")
		#
		else:
			raise XCPLException("Syntax Error")
	#
	#		Check next token
	#		
	def checkNext(self,stream,t):
		if stream.get() != t:
			raise XCPLException("Missing '"+t+"'")
	#
	#		Check if token is identifier
	#
	def isIdentifier(self,t):
		return t[0] >= 'a' and t[0] <= 'z'
	#
	#		Get current PC address
	#
	def getAddress(self):
		return self.cg.getCodePointer()
	#
	#		Compile a branch
	#
	def compileBranch(self,branchType = ""):
		addr = self.getAddress()												# where the branch is
		if branchType == "":													# compile the appropriate branch
			self.cg.c_br(0)
		elif branchType == "NZ":
			self.cg.c_brnz(0)
		elif branchType == "Z":
			self.cg.c_brz(0)
		else:
			assert False
		return addr
	#
	#		Patch a branch
	#
	def patchBranch(self,branchAddr,targetAddr):
		offset = targetAddr - (branchAddr+1)									# offset
		if offset < -128 or offset > 127:										# how big is the offset
			raise XCPLException("Loop is too large")
		self.cg.write(branchAddr+1,offset & 0xFF)								# patch it up.



if __name__ == "__main__":
	ic = InstructionCompiler(CodeGen(X16CodeGen(1024,1024)),IdentStore())
	stream = TextParser("""
		 { 
		 	var c,d[128];
		 	var star;star = 42;
		 	print.char(star);
		 	do (60000) {
		 	} print.char(star);
		 }
	""".strip().split("\n"))

	codeStart = ic.cg.getCodePointer()
	ic.cg.setExecuteAddress(codeStart)
	ic.cg.setListHandle()

	ic.compile(stream)
	ic.compile(stream)

	print("............")
	ic.cg.c_xeq()
	p = ic.cg.getCodePointer()
	ic.cg.c_lcw(0,0xFFFF)
	ic.cg.write(p+0,0xEA)
	ic.cg.write(p+1,0x80)
	ic.cg.write(p+2,0xFE)
	ic.cg.writeProgram("test.prg")
