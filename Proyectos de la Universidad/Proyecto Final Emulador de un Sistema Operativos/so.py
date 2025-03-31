#!/usr/bin/env python

from hardware import *
import log
import heapq
import math



## emulates a compiled program
class Program():

    def __init__(self, name, instructions):
        self._name = name
        self._instructions = self.expand(instructions)

    @property
    def name(self):
        return self._name

    @property
    def instructions(self):
        return self._instructions

    def addInstr(self, instruction):
        self._instructions.append(instruction)

    def expand(self, instructions):
        expanded = []
        for i in instructions:
            if isinstance(i, list):
                ## is a list of instructions
                expanded.extend(i)
            else:
                ## a single instr (a String)
                expanded.append(i)

        ## now test if last instruction is EXIT
        ## if not... add an EXIT as final instruction
        last = expanded[-1]
        if not ASM.isEXIT(last):
            expanded.append(INSTRUCTION_EXIT)

        return expanded

    def __repr__(self):
        return "Program({name}, {instructions})".format(name=self._name, instructions=self._instructions)


## emulates an Input/Output device controller (driver)
class IoDeviceController():

    def __init__(self, device):
        self._device = device
        self._waiting_queue = []
        self._currentPCB = None
    
    @property
    def waiting_queue(self):
        return self._waiting_queue

    def runOperation(self, pcb, instruction):
        pair = {'pcb': pcb, 'instruction': instruction}
        # append: adds the element at the end of the queue
        self._waiting_queue.append(pair)
        # try to send the instruction to hardware's device (if is idle)
        self.__load_from_waiting_queue_if_apply()

    def getFinishedPCB(self):
        finishedPCB = self._currentPCB
        self._currentPCB = None
        self.__load_from_waiting_queue_if_apply()
        return finishedPCB

    def __load_from_waiting_queue_if_apply(self):
        if (len(self._waiting_queue) > 0) and self._device.is_idle:
            ## pop(): extracts (deletes and return) the first element in queue
            pair = self._waiting_queue.pop(0)
            pcb = pair['pcb']
            instruction = pair['instruction']
            self._currentPCB = pcb
            self._device.execute(instruction)


    def __repr__(self):
        return "IoDeviceController for {deviceID} running: {currentPCB} waiting: {waiting_queue}".format(deviceID=self._device.deviceId, currentPCB=self._currentPCB, waiting_queue=self._waiting_queue)

NEW = "new"
WAITING = "waiting"
READY = "ready"
RUNNING = "running"
TERMINATED = "terminated"

class Loader():
    
    def __init__(self, mm, kernel):
        self._kernel = kernel
        self._memoryManager = mm
        self._pageTable = []  #lista donde cada tupla tiene el nombre y la pageTable de cada programa
        #ejemplo: pageTable = [ (prog.1,[(1,3),(2,6),(3,7)]) , (prog.2,[(1,2),(2,5),(3,8)]) , (prog.5,[(1,1),(2,5)]) ]

    def load(self, program):
        instrucciones = program.instructions
        progSize = len(instrucciones)
        cantFrames = math.ceil(progSize / self._kernel.frameSize) # redondea la division hacia arriba
        print("CANTIDAD DE FRAMES NECESARIOS PARA {name}:".format(name=program.name), cantFrames)
        #en algunos casos da un frame menos del que necesita, ¿solucion?

        freeFrames = self._memoryManager.allocFrame(cantFrames)
        listaProg = [] # pageTable de solo un programa [(page, frame),(page,frame)]
        page = 0
        for f in freeFrames: # carga las paginas del programa en los frames dados
            for index in range (0, self._kernel.frameSize): # de a un frame por vez
                if len(instrucciones) > 0:
                    inst = instrucciones.pop(0)
                    HARDWARE.memory.write(f[1] + index, inst)
            listaProg.append((page, f)) # agrega cada pagina con su frame
            page += 1
        self._pageTable.append((program.name ,listaProg)) # se guarda el nombre del program y su mapeo(pagina y frame)
        return (listaProg)  #ya no devuelve solo base dir, sino que la pageTable de ese programa
    
    @property
    def pageTable(self):
        return self._pageTable
    
    @pageTable.setter
    def pageTable(self, pT):
        self._pageTable = pT

class Dispatcher():
    def __init__(self, kernel):
        self._kernel = kernel
    
    def load(self, pcb):
        log.logger.info("\n Executing program: {name}".format(name=pcb.programName))
        HARDWARE.cpu.pc = pcb.pc
        HARDWARE.mmu.resetTLB()
        for pageFrame in pcb.pageTable:  #ejecuta pagina por pagina hasta la ultima
            page = pageFrame[0]
            frameID = pageFrame[1][0] # segundo valor de pageFrame = Frame, primer valor de Frame = FrameID  #(1,(2,4))
            HARDWARE.mmu.setPageFrame(page, frameID)
        HARDWARE.timer.reset()
    
    def save(self, pcb):
        pcb.pc = HARDWARE.cpu.pc
        HARDWARE.cpu.pc = -1
        
class PCB():
    
    def __init__(self, pid, pageTable, programName, priority):
        self._pid = pid
        self._pageTable = pageTable #cambio aca(ex baseDir) [(page, frame),(page,frame)]
        self._programName = programName
        self._state = NEW
        self._pc = 0
        self._originalPriority = priority
        self._currentPriority = priority
    
    @property
    def pid(self):
        return self._pid
    
    @property
    def pageTable(self):
        return self._pageTable
    
    @property
    def programName(self):
        return self._programName
    
    def setState(self, newState):
        self._state = newState
    
    @property
    def currentPriority(self):
        return self._currentPriority
    
    @currentPriority.setter
    def currentPriority(self, newPriority):
        self._currentPriority = newPriority
    
    @property
    def originalPriority(self):
        return self._originalPriority
    
    def __lt__(self, other):
        return self._currentPriority < other._currentPriority


    @property
    def pc(self):
        return self._pc
    
    @pc.setter
    def pc(self, newPc):
        self._pc = newPc

class PCBTable():
    
    def __init__(self):
        self._PCBTable = []
        self._newPID = 1
        self._runningPCB = None
    
    def getPCB(self, PID):
        pass
    
    def addPCB(self, PCB):
        self._PCBTable.append(PCB)
        self._newPID = self._newPID + 1
    
    @property
    def runningPCB(self):
        return self._runningPCB
    
    @runningPCB.setter
    def runningPCB(self, newRunningPCB):
        self._runningPCB = newRunningPCB
        if self._runningPCB:
            self._runningPCB.setState(RUNNING)
    
    @property
    def getNewPID(self):
        return self._newPID


## emulates the  Interruptions Handlers
class AbstractInterruptionHandler():
    def __init__(self, kernel):
        self._kernel = kernel

    @property
    def kernel(self):
        return self._kernel

    def execute(self, irq):
        log.logger.error("-- EXECUTE MUST BE OVERRIDEN in class {classname}".format(classname=self.__class__.__name__))


class KillInterruptionHandler(AbstractInterruptionHandler):

    def execute(self, irq):
        
        pcb = self.kernel.pcbTable.runningPCB
        self.kernel.dispatcher.save(pcb)
        pcb.state = TERMINATED

        # no implmentado self.kernel.pcbTable.removePCB(pcb)
        # self.kernel.loader.pageTable.remove(pcb.programName)

        self.kernel._memoryManager.liberarMemoria(pcb.pageTable)

        if self.kernel.scheduler.readyQueue:
            pcbToLoad = self.kernel.scheduler.getNext()
            self.kernel.pcbTable.runningPCB = pcbToLoad
            self.kernel.dispatcher.load(pcbToLoad)
        else:
            self.kernel.pcbTable.runningPCB = None
            HARDWARE.cpu.pc = -1
            
        if not (self.kernel.scheduler.readyQueue) and HARDWARE.ioDevice.is_idle and not self.kernel.pcbTable.runningPCB:
            log.logger.info(" Program Finished ")
            HARDWARE.switchOff()

class IoInInterruptionHandler(AbstractInterruptionHandler):

    def execute(self, irq):
        
        operation = irq.parameters
        pcb = self.kernel.pcbTable.runningPCB
        self.kernel.dispatcher.save(pcb)
        pcb.setState(WAITING)
        self.kernel.ioDeviceController.runOperation(pcb, operation)
        
        if self.kernel.scheduler.readyQueue:
            pcbToLoad = self.kernel.scheduler.getNext()
            self.kernel.pcbTable.runningPCB = pcbToLoad
            self.kernel.dispatcher.load(pcbToLoad)
        else:
            self.kernel.pcbTable.runningPCB = None
            HARDWARE.cpu.pc = -1

class IoOutInterruptionHandler(AbstractInterruptionHandler):

    def execute(self, irq):
        
        pcbInCPU = self.kernel.pcbTable.runningPCB
        pcbToAdd = self.kernel.ioDeviceController.getFinishedPCB()
        
        if self.kernel.pcbTable.runningPCB:
            if self.kernel.scheduler.mustExpropiate(pcbInCPU, pcbToAdd):
                self.kernel.dispatcher.save(pcbInCPU)
                self.kernel.scheduler.addPCB(pcbInCPU)
                
                self.kernel.dispatcher.load(pcbToAdd)
                self.kernel.pcbTable.runningPCB = pcbToAdd
            else:
                self.kernel.scheduler.addPCB(pcbToAdd)
        else:
            self.kernel.dispatcher.load(pcbToAdd)
            self.kernel.pcbTable.runningPCB = pcbToAdd

class NewInterruptionHandler(AbstractInterruptionHandler):
    
    def execute(self, irq):
        parameters = irq.parameters
        path = parameters['program']
        priority = parameters['priority']
        pid = self.kernel.pcbTable.getNewPID
        program = self._kernel.fileSystem.read(path)
        pageTable = self.kernel.loader.load(program)

        newPCB = PCB(pid, pageTable, program.name, priority)
        self.kernel.pcbTable.addPCB(newPCB)

        if self.kernel.pcbTable.runningPCB:
            self.kernel.scheduler.addPCB(newPCB)
        else:
            self.kernel.dispatcher.load(newPCB)
            self.kernel.pcbTable.runningPCB = newPCB
            
class TimeoutInterruptionHandler(AbstractInterruptionHandler):
    
    def execute(self, irq):
        
        if self.kernel.scheduler.readyQueue:
            pcbToAdd = self.kernel.pcbTable.runningPCB
            self.kernel.dispatcher.save(pcbToAdd)
            self.kernel.scheduler.addPCB(pcbToAdd)
            
            pcbToLoad = self.kernel.scheduler.getNext()
            self.kernel.pcbTable.runningPCB = pcbToLoad
            self.kernel.dispatcher.load(pcbToLoad)
        else:
            HARDWARE.timer.reset()

class AbstractScheduler():
    
    def __init__(self):
        self._readyQueue = []
        
    def addPCB(self, pcb):
        log.logger.error("-- ADDPCB MUST BE OVERRIDEN in class {classname}".format(classname=self.__class__.__name__))
        
    def getNext(self):
        log.logger.error("-- GETNEXT MUST BE OVERRIDEN in class {classname}".format(classname=self.__class__.__name__))
        
    def mustExpropiate(self, pcbInCPU, pcbToAdd):
        log.logger.error("-- MUSTEXPROPIATE MUST BE OVERRIDEN in class {classname}".format(classname=self.__class__.__name__))
    
    @property
    def readyQueue(self):
        return self._readyQueue
    
class FCFSScheduler(AbstractScheduler):
    
    def addPCB(self, pcb):
        self._readyQueue.append(pcb)
        pcb.setState(READY)
        
    def getNext(self):
        return self._readyQueue.pop(0)
    
    def mustExpropiate(self, pcbInCPU, pcbToAdd):
        return False
        
class NoPreemptivePriorityScheduler(AbstractScheduler):

    def addPCB(self, pcb):
        heapq.heappush(self._readyQueue, (pcb.originalPriority, pcb))
        pcb.setState(READY)
        pcb.currentPriority = pcb.originalPriority

    def getNext(self):
        nextPCB = self._readyQueue.pop(0)[1]
        progSize = len(self._readyQueue)
        for index in range(0, progSize):
            print("aumentando prioridad de", self._readyQueue[index][1].programName)
            self._readyQueue[index][1].currentPriority = self._readyQueue[index][0] - 1
            self._readyQueue[index] = (self._readyQueue[index][1].currentPriority, self._readyQueue[index][1])
        return nextPCB
    
    def mustExpropiate(self, pcbInCPU, pcbToAdd):
        return False
            
class PreemptivePriorityScheduler(NoPreemptivePriorityScheduler):
    
    def mustExpropiate(self, pcbInCPU, pcbToAdd):
        return pcbToAdd.currentPriority < pcbInCPU.currentPriority
    
class RoundRobinScheduler(FCFSScheduler):
    
    def __init__(self, quantum):
        super().__init__()
        HARDWARE.timer.quantum = quantum

# emulates the core of an Operative System
class Kernel():

    def __init__(self):
        ## setup interruption handlers
        killHandler = KillInterruptionHandler(self)
        HARDWARE.interruptVector.register(KILL_INTERRUPTION_TYPE, killHandler)

        ioInHandler = IoInInterruptionHandler(self)
        HARDWARE.interruptVector.register(IO_IN_INTERRUPTION_TYPE, ioInHandler)

        ioOutHandler = IoOutInterruptionHandler(self)
        HARDWARE.interruptVector.register(IO_OUT_INTERRUPTION_TYPE, ioOutHandler)
        
        newHandler = NewInterruptionHandler(self)
        HARDWARE.interruptVector.register(NEW_INTERRUPTION_TYPE, newHandler)
        
        timeoutHandler = TimeoutInterruptionHandler(self)
        HARDWARE.interruptVector.register(TIMEOUT_INTERRUPTION_TYPE, timeoutHandler)

        ## controls the Hardware's I/O Device
        self._ioDeviceController = IoDeviceController(HARDWARE.ioDevice)

        self._frameSize = 4
        self._memoryManager = MemoryManager(self)
        self._loader = Loader(self._memoryManager, self)
        self._dispatcher = Dispatcher(self)
        self._pcbTable = PCBTable()
        self._scheduler = NoPreemptivePriorityScheduler()
        
        HARDWARE.mmu.frameSize = self.frameSize
        self._fileSystem = FileSystem()
        
    @property
    def fileSystem(self):
        return self._fileSystem


    @property
    def ioDeviceController(self):
        return self._ioDeviceController
    
    @property
    def loader(self):
        return self._loader
    
    @property
    def memoryManager(self):
        return self._memoryManager

    @property
    def dispatcher(self):
        return self._dispatcher
    
    @property
    def pcbTable(self):
        return self._pcbTable
    
    @property
    def scheduler(self):
        return self._scheduler
    
    @property
    def frameSize(self):
        return self._frameSize

    ## emulates a "system call" for programs execution
    def run(self, programPath , priority):
        parameters = {'program': programPath, 'priority': priority}
        newIRQ = IRQ(NEW_INTERRUPTION_TYPE, parameters)
        HARDWARE.interruptVector.handle(newIRQ)
        log.logger.info(HARDWARE)

    def __repr__(self):
        return "Kernel "
    
class MemoryManager():

    def __init__(self, kernel):
        self._kernel = kernel
        self._memory = HARDWARE.memory
        self._memorySize = HARDWARE.memory.size
        self._freeFrames = self.createFrames()
        self._ocupatedFrames = []

    @property
    def memory(self):
        return self._memory
    
    @property
    def memorySize(self):
        return self._memorySize

    @property
    def ocupatedFrames(self):
        return self._ocupatedFrames

    @property
    def freeFrames(self):
        return self._freeFrames
    
    def createFrames(self):
        freeS= []
        for index in range(0, int(self._memorySize / self._kernel.frameSize)): # GARANTIZAMOS LA DIVISION ENTERA
            freeS.append((index, index * self._kernel.frameSize))   # crea una tupla con el id del frame y su baseDir
        log.logger.info("CREANDO FRAMES...")
        log.logger.info("\n frames libres: {name}".format(name=freeS))
        return(freeS)
    
    def allocFrame2(self, cantFrames):
        frames = []
        it = cantFrames
        while(it != 0):
            frame = self.freeFrames.pop(0)
            frames.append(frame)
            self.ocupatedFrames.append(frame)
            it =-1
            self._memorySize =- self._kernel.frameSize
        log.logger.info("ASIGNANDO FRAMES...")   
        return frames
    
    def allocFrame(self, cantFrames):
        if len(self.freeFrames) >= cantFrames:
            frames = []
            for _ in range(cantFrames):
                frame = self.freeFrames.pop(0)
                frames.append(frame)
                self.ocupatedFrames.append(frame)
                self._memorySize -= self._kernel.frameSize
            log.logger.info("ASIGNANDO FRAMES...")
            log.logger.info("\n frames libres: {name}".format(name=self.freeFrames)) 
            log.logger.info("\n frames ocupados: {name}".format(name=self.ocupatedFrames)) 
            return frames
        else:
            log.logger.error("NO HAY SUFICIENTES FRAMES LIBRES")
        

    def liberarMemoria(self, pageTable):
        for pageFrame in pageTable:
            self._freeFrames.append(pageFrame[1])
            self.ocupatedFrames.remove(pageFrame[1])
            self._memorySize += self._kernel.frameSize
        log.logger.info("LIBERANDO FRAMES...")
        log.logger.info("\n frames libres: {name}".format(name=self.freeFrames)) 
        log.logger.info("\n frames ocupados: {name}".format(name=self.ocupatedFrames))


class FileSystem():

    def __init__(self):
        self._archive = dict()

    @property
    def archive(self):
        return self._archive

    def write(self, path, prg):
        self.archive[path] = prg

    def read(self, path):
        return self.archive[path]
    