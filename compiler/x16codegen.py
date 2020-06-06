# *****************************************************************************
# *****************************************************************************
#
#		Name:		x16codegen.py
#		Purpose:	Base Code Generator
#		Date: 		6th June 2020
#		Author:		Paul Robson (paul@robsons.org.uk)
#
# *****************************************************************************
# *****************************************************************************

from error import *
from sour16 import *

# *****************************************************************************
#
#							Code Generator (Commander X16)
#
# *****************************************************************************

class X16CodeGen(object):
	#
	#		Initialisation. Copies the run time, and allocates uninitialised and initialised
	#		Data memory
	#
	def __init__(self,uninitSize,initSize):
		self.code = [x for x in Sour16.RUNTIME]									# code object
		self.base = Sour16.LOADADDR 											# the load address
		self._setupMemoryUsage(uninitSize,initSize)
		self.codeStart = self.codePtr
	#
	#		Sets up how memory is allocated for this specific machine. This simply
	#		puts the initialised data, then the uninitialised, then the code.		
	#
	def _setupMemoryUsage(self,uninitSize,initSize):
		#
		self.iPointer = self.code[8]+self.code[9]*256 							# initialised data
		self.iLimit = self.iPointer + initSize 									# space
		#
		self.uPointer = self.iLimit												# uninitialised data space
		self.uLimit = self.uPointer + uninitSize
		#
		self.codePtr = self.uLimit 												# where code actually goes.
		self.codeLimit = 0x9F00													# where it ends.
	#
	#		Allocate Uninitialised Data Memory
	#
	def allocUninitialised(self,size):
		addr = self.uPointer
		self.uPointer += size
		if self.uPointer >= self.uLimit:
			raise XCPLException("Out of uninitialised data memory")
	#
	#		Write a byte to initialised data memory.
	#
	def writeDataMemory(self,data):
		if self.iPointer == self.iLimit:										# out of memory
			raise XCPLException("Out of initialised data Memory")
		self.write(self.iPointer,data)											# write and bump pointer
		self.iPointer += 1
		return self.iPointer-1
	#
	#		Set the execute address
	#
	def setExecuteAddress(self,address):
		assert address >= self.codeStart and address < self.codePtr
		self.code[4] = address & 0xFF
		self.code[5] = (address >> 8) & 0xFF
	#
	#		Write to the code base.
	#
	def write(self,address,data):
		assert address >= self.base and address < 0x10000
		assert data >= 0 and data < 0x100
		if False:
			print("\t${0:04x} ${1:02x}".format(address,data))
		address = address - self.base 											# offset in data
		while len(self.code) < address+1: 										# pad it out if required
			self.code.append(0xFF)
		self.code[address] = data 	
	#
	#		Instruction writers.
	#
	def assemble(self,opcode,operandSize = 0,operand = None):
		addr = self.codePtr
		self.write(self.codePtr,opcode) 										# write to memory
		if operandSize >= 1:
			self.write(self.codePtr+1,operand & 0xFF)
		if operandSize >= 2:
			self.write(self.codePtr+2,(operand >> 8) & 0xFF)
		#
		if True:																# code listing.
			operand = 0 if operand is None else operand
			s = [ opcode, operand & 0xFF,(operand >> 8) & 0xFF ][:operandSize+1]
			s = " ".join(["{0:02x}".format(x) for x in s])
			c = Sour16.DECODE[opcode].replace("@","r"+str(opcode & 15)).replace("#","${0:04x}".format(operand))
			if c.find("+"):
				a = self.codePtr+1+(operand if (operand & 0x80) == 0 else (operand & 0xFF)-256)
				c = c.replace("+","${0:04x}".format(a))	
			c = c.split() + [ "" ]
			print("{0:04x} : {1:10} : {2:8} {3}".format(self.codePtr,s,c[0],c[1]))
		#
		self.codePtr += (operandSize + 1)										# advance code pointer
		if self.codePtr >= self.codeLimit:
			raise XCPLException("Out of program memory.")
		return addr 
		
if __name__ == "__main__":
	cg = X16CodeGen(1024,1024)
	cg.assemble(16,2,32765)
	cg.assemble(48,0)
	cg.assemble(8,1,-2)