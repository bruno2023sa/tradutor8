
import os

COMMENT = '//'


class Parser(object):
    def __init__(self, vm_filename):
        self.vm_filename = vm_filename
        self.vm = open(vm_filename, 'r')
        self.EOF = False
        self.commands = self.commands_dict()
        self.curr_instruction = None
        self.initialize_file()

    def advance(self):
        self.curr_instruction = self.next_instruction
        self.load_next_instruction()

    @property
    def has_more_commands(self):
        return not self.EOF

    @property
    def command_type(self):
        return self.commands.get(self.curr_instruction[0].lower())

    @property
    def arg1(self):
        '''Math operation if C_ARITHMETIC'''
        if self.command_type == 'C_ARITHMETIC':
            return self.argn(0)
        return self.argn(1)

    @property
    def arg2(self):
        '''Only return if C_PUSH, C_POP, C_FUNCTION, C_CALL'''
        return self.argn(2)

    def close(self):
        self.vm.close()

    def initialize_file(self):
        self.vm.seek(0)
        self.load_next_instruction()

    def load_next_instruction(self, line=None):
        loaded = False
        while not loaded and not self.EOF:
            tell = self.vm.tell()
            line = self.vm.readline().strip()
            if self.is_instruction(line):
                self.next_instruction = line.split(COMMENT)[0].strip().split()
                loaded = True
            if tell == self.vm.tell(): 
                self.EOF = True

    def is_instruction(self, line):
        return line and line[:2] != COMMENT

    def argn(self, n):
        if len(self.curr_instruction) >= n+1:
            return self.curr_instruction[n]
        return None

    def commands_dict(self):
        return {
            'add': 'C_ARITHMETIC',
            'sub': 'C_ARITHMETIC',
            'neg': 'C_ARITHMETIC',
             'eq': 'C_ARITHMETIC',
             'gt': 'C_ARITHMETIC',
             'lt': 'C_ARITHMETIC',
            'and': 'C_ARITHMETIC',
             'or': 'C_ARITHMETIC',
            'not': 'C_ARITHMETIC',
           'push': 'C_PUSH',
            'pop': 'C_POP',
          'label': 'C_LABEL',
           'goto': 'C_GOTO',
        'if-goto': 'C_IF',
       'function': 'C_FUNCTION',
         'return': 'C_RETURN',
           'call': 'C_CALL'
        }


class CodeWriter(object):
    
    def __init__(self, asm_filename):
        self.asm = open(asm_filename, 'w')
        self.curr_file = None
        self.addresses = self.address_dict()
        self.line_count = 0
        self.bool_count = 0 
        self.call_count = 0 

    
    def write_init(self):
        self.write('@256')
        self.write('D=A')
        self.write('@SP')
        self.write('M=D')
        self.write_call('Sys.init', 0)
        

    def set_file_name(self, vm_filename):
        '''Reset pointers'''
        self.curr_file = vm_filename.replace('.vm', '').split('/')[-1]
    
        self.write('//////', code=False)
        self.write('// {}'.format(self.curr_file), code=False)

    def write_arithmetic(self, operation):
        '''Apply operation to top of stack'''
        if operation not in ['neg', 'not']: 
            self.pop_stack_to_D()
        self.decrement_SP()
        self.set_A_to_stack()

        if operation == 'add': 
            self.write('M=M+D')
        elif operation == 'sub':
            self.write('M=M-D')
        elif operation == 'and':
            self.write('M=M&D')
        elif operation == 'or':
            self.write('M=M|D')
        elif operation == 'neg':
            self.write('M=-M')
        elif operation == 'not':
            self.write('M=!M')
        elif operation in ['eq', 'gt', 'lt']: 
            self.write('D=M-D')
            self.write('@BOOL{}'.format(self.bool_count))

            if operation == 'eq':
                self.write('D;JEQ') 
            elif operation == 'gt':
                self.write('D;JGT') 
            elif operation == 'lt':
                self.write('D;JLT') 

            self.set_A_to_stack()
            self.write('M=0')
            self.write('@ENDBOOL{}'.format(self.bool_count))
            self.write('0;JMP')

            self.write('(BOOL{})'.format(self.bool_count), code=False)
            self.set_A_to_stack()
            self.write('M=-1') 

            self.write('(ENDBOOL{})'.format(self.bool_count), code=False)
            self.bool_count += 1
        else:
            self.raise_unknown(operation)
        self.increment_SP()

    def write_push_pop(self, command, segment, index):
        self.resolve_address(segment, index)
        if command == 'C_PUSH': 
            if segment == 'constant':
                self.write('D=A')
            else:
                self.write('D=M')
            self.push_D_to_stack()
        elif command == 'C_POP': 
            self.write('D=A')
            self.write('@R13') 
            self.write('M=D')
            self.pop_stack_to_D()
            self.write('@R13')
            self.write('A=M')
            self.write('M=D')
        else:
            self.raise_unknown(command)

    def write_label(self, label):
        self.write('({}${})'.format(self.curr_file, label), code=False)

    def write_goto(self, label):
        self.write('@{}${}'.format(self.curr_file, label))
        self.write('0;JMP')

    def write_if(self, label):
        self.pop_stack_to_D()
        self.write('@{}${}'.format(self.curr_file, label))
        self.write('D;JNE')

    def write_function(self, function_name, num_locals):
        self.write('({})'.format(function_name), code=False)

        for _ in xrange(num_locals): 
            self.write('D=0')
            self.push_D_to_stack()

    def write_call(self, function_name, num_args):
        RET = function_name + 'RET' +  str(self.call_count) 
        self.call_count += 1

        
        self.write('@' + RET)
        self.write('D=A')
        self.push_D_to_stack()

        
        for address in ['@LCL', '@ARG', '@THIS', '@THAT']:
            self.write(address)
            self.write('D=M')
            self.push_D_to_stack()

        self.write('@SP')
        self.write('D=M')
        self.write('@LCL')
        self.write('M=D')

        self.write('@' + str(num_args + 5))
        self.write('D=D-A')
        self.write('@ARG')
        self.write('M=D')

        self.write('@' + function_name)
        self.write('0;JMP')

        self.write('({})'.format(RET), code=False)

    def write_return(self):
        FRAME = 'R13'
        RET = 'R14'

        self.write('@LCL')
        self.write('D=M')
        self.write('@' + FRAME)
        self.write('M=D')

        self.write('@' + FRAME)
        self.write('D=M') 
        self.write('@5')
        self.write('D=D-A') 
        self.write('A=D') 
        self.write('D=M') 
        self.write('@' + RET)
        self.write('M=D') 

        self.pop_stack_to_D()
        self.write('@ARG')
        self.write('A=M')
        self.write('M=D')

        self.write('@ARG')
        self.write('D=M')
        self.write('@SP')
        self.write('M=D+1')

        
        offset = 1
        for address in ['@THAT', '@THIS', '@ARG', '@LCL']:
            self.write('@' + FRAME)
            self.write('D=M') 
            self.write('@' + str(offset))
            self.write('D=D-A') 
            self.write('A=D') 
            self.write('D=M') 
            self.write(address)
            self.write('M=D') 
            offset += 1

        
        self.write('@' + RET)
        self.write('A=M')
        self.write('0;JMP')

    
    def write(self, command, code=True):
        self.asm.write(command)
        if code:
            self.asm.write(' // ' + str(self.line_count))
            self.line_count += 1
        self.asm.write('\n')

    def close(self):
        self.asm.close()

    def raise_unknown(self, argument):
        raise ValueError('{} is an invalid argument'.format(argument))

    def resolve_address(self, segment, index):
        '''Resolve address to A register'''
        address = self.addresses.get(segment)
        if segment == 'constant':
            self.write('@' + str(index))
        elif segment == 'static':
            self.write('@' + self.curr_file + '.' + str(index))
        elif segment in ['pointer', 'temp']:
            self.write('@R' + str(address + index)) 
        elif segment in ['local', 'argument', 'this', 'that']:
            self.write('@' + address) 
            self.write('D=M')
            self.write('@' + str(index))
            self.write('A=D+A') 
        else:
            self.raise_unknown(segment)

    def address_dict(self):
        return {
            'local': 'LCL', 
            'argument': 'ARG', 
            'this': 'THIS', 
            'that': 'THAT', 
            'pointer': 3, 
            'temp': 5, 
            
            'static': 16, 
        }

    def push_D_to_stack(self):
        '''Push from D onto top of stack, increment @SP'''
        self.write('@SP') 
        self.write('A=M') 
        self.write('M=D') 
        self.increment_SP()

    def pop_stack_to_D(self):
        '''Decrement @SP, pop from top of stack onto D'''
        self.decrement_SP()
        self.write('A=M') 
        self.write('D=M') 

    def decrement_SP(self):
        self.write('@SP')
        self.write('M=M-1')

    def increment_SP(self):
        self.write('@SP')
        self.write('M=M+1')

    def set_A_to_stack(self):
        self.write('@SP')
        self.write('A=M')


class Main(object):
    def __init__(self, file_path):
        self.parse_files(file_path)
        self.cw = CodeWriter(self.asm_file)
        self.cw.write_init()
        for vm_file in self.vm_files:
            self.translate(vm_file)
        self.cw.close()

    def parse_files(self, file_path):
        if '.vm' in file_path:
            self.asm_file = file_path.replace('.vm', '.asm')
            self.vm_files = [file_path]
        else:
            file_path = file_path[:-1] if file_path[-1] == '/' else file_path
            path_elements = file_path.split('/')
            path = '/'.join(path_elements)
            self.asm_file = path + '/' + path_elements[-1] + '.asm'
            dirpath, dirnames, filenames = next(os.walk(file_path), [[],[],[]])
            vm_files = filter(lambda x: '.vm' in x, filenames)
            self.vm_files = [path + '/' +  vm_file for vm_file in vm_files]

    def translate(self, vm_file):
        parser = Parser(vm_file)
        self.cw.set_file_name(vm_file)
        while parser.has_more_commands:
            parser.advance()
            self.cw.write('// ' + ' '.join(parser.curr_instruction), code=False)
            if parser.command_type == 'C_PUSH':
                self.cw.write_push_pop('C_PUSH', parser.arg1, int(parser.arg2))
            elif parser.command_type == 'C_POP':
                self.cw.write_push_pop('C_POP', parser.arg1, int(parser.arg2))
            elif parser.command_type == 'C_ARITHMETIC':
                self.cw.write_arithmetic(parser.arg1)
            elif parser.command_type == 'C_LABEL':
                self.cw.write_label(parser.arg1)
            elif parser.command_type == 'C_GOTO':
                self.cw.write_goto(parser.arg1)
            elif parser.command_type == 'C_IF':
                self.cw.write_if(parser.arg1)
            elif parser.command_type == 'C_FUNCTION':
                self.cw.write_function(parser.arg1, int(parser.arg2))
            elif parser.command_type == 'C_CALL':
                self.cw.write_call(parser.arg1, int(parser.arg2))
            elif parser.command_type == 'C_RETURN':
                self.cw.write_return()
        parser.close()


if __name__ == '__main__':
    import sys

    file_path = sys.argv[1]
    Main(file_path)