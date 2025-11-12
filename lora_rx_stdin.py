#!/usr/bin/env python3

import sys
import select
import numpy as np
import time
from gnuradio import gr, blocks
import pmt

sys.path.insert(0, '/usr/local/lib/python3.9/site-packages/gnuradio')
import lora_sdr

# КОНФИГУРАЦИЯ ПАРАМЕТРОВ LoRa - ПРАВИЛЬНЫЙ ПОРЯДОК из сигнатуры!
CONFIG = {
    'center_freq': 869100000,      # 1-й параметр: Центральная частота
    'bw': 125000,                  # 2-й параметр: Полоса пропускания
    'cr': 2,                       # 3-й параметр: Coding Rate (2 = 4/6)
    'has_crc': True,               # 4-й параметр: CRC проверка
    'impl_head': False,            # 5-й параметр: Тип заголовка
    'pay_len': 255,                # 6-й параметр: Длина полезной нагрузки
    'samp_rate': 250000,           # 7-й параметр: Частота дискретизации
    'sf': 7,                       # 8-й параметр: Spreading Factor
    'sync_word': [0x34],           # 9-й параметр: Синхрослово
    'soft_decoding': False,        # 10-й параметр: Мягкое декодирование
    'ldro_mode': 2,                # 11-й параметр: Режим низкой скорости
    'print_rx': [True, True]       # 12-й параметр: Диагностический вывод
}

class StdinToVectorSource(gr.sync_block):
    def __init__(self, item_size):
        gr.sync_block.__init__(
            self,
            name="StdinToVectorSource",
            in_sig=None,
            out_sig=[np.complex64]
        )
        self.item_size = item_size
        self.last_debug_time = 0
        self.total_samples_received = 0
        self.start_time = time.time()
        
    def work(self, input_items, output_items):
        out = output_items[0]
        bytes_to_read = len(out) * 8
        
        current_time = time.time()
        
        # Отладочный вывод каждые 5 секунд
        if current_time - self.last_debug_time >= 5.0:
            elapsed = current_time - self.start_time
            rate = self.total_samples_received / elapsed if elapsed > 0 else 0
            #print(f"DEBUG: Samples: {self.total_samples_received:,}, Rate: {rate:.0f}/sec", file=sys.stderr)
            self.last_debug_time = current_time
        
        try:
            if select.select([sys.stdin], [], [], 0.0)[0]:
                data = sys.stdin.buffer.read(bytes_to_read)
                if data:
                    samples = np.frombuffer(data, dtype=np.complex64)
                    n = min(len(samples), len(out))
                    out[:n] = samples[:n]
                    self.total_samples_received += n
                    return n
        except (IOError, BlockingIOError):
            pass
            
        return 0

class MessageToStdout(gr.basic_block):
    def __init__(self):
        gr.basic_block.__init__(
            self,
            name="MessageToStdout", 
            in_sig=None,
            out_sig=None
        )
        self.message_port_register_in(pmt.intern("in"))
        self.set_msg_handler(pmt.intern("in"), self.handle_msg)    
    def handle_msg(self, msg):
        try:
            data = pmt.to_python(msg)
            # В stdout - чистый текст сообщения для TextParser
            print(data)
            # В stderr - отладочная информация  
            print(f"DEBUG: Successfully decoded message: {data}", file=sys.stderr)
        except Exception as e:
            print(f"DEBUG: Failed to decode message: {e}", file=sys.stderr)
        sys.stdout.flush()
        return True

def main():
    print("=== LoRa Receiver STARTING ===", file=sys.stderr)
    print(f"Freq: {CONFIG['center_freq']}Hz, SF{CONFIG['sf']}, BW:{CONFIG['bw']}Hz, CR:4/{CONFIG['cr']+4}", file=sys.stderr)
    print(f"Sync: 0x{CONFIG['sync_word'][0]:02X}, CRC: {CONFIG['has_crc']}", file=sys.stderr)
    
    tb = gr.top_block()
    
    source = StdinToVectorSource(item_size=gr.sizeof_gr_complex)
    source.set_output_multiple(8020)  # Оптимальный размер
    
    # Декодер LoRa с ПРАВИЛЬНЫМ порядком параметров
    lora_receiver = lora_sdr.lora_sdr_lora_rx(
        CONFIG['center_freq'],  # 1
        CONFIG['bw'],           # 2  
        CONFIG['cr'],           # 3
        CONFIG['has_crc'],      # 4
        CONFIG['impl_head'],    # 5
        CONFIG['pay_len'],      # 6
        CONFIG['samp_rate'],    # 7
        CONFIG['sf'],           # 8
        CONFIG['sync_word'],    # 9
        CONFIG['soft_decoding'],# 10
        CONFIG['ldro_mode'],    # 11
        CONFIG['print_rx']      # 12
    )
    
    message_output = MessageToStdout()
    
    tb.connect(source, lora_receiver)
    tb.msg_connect((lora_receiver, 'out'), (message_output, 'in'))
    
    print("=== Waiting for LoRa packets... ===", file=sys.stderr)
    tb.run()
    
    print("=== LoRa Receiver STOPPED ===", file=sys.stderr)

if __name__ == '__main__':
    main()