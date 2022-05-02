CC = gcc
CFLAGS = -g
LDLIBS = -lm

ifdef DEBUG
	CFLAGS += -DDEBUG
endif

all: reader

reader: reader.o bme680.o bsec_integration.o bsec_serialized_configurations_iaq.o libalgobsec.a

reader.o: reader.c
bme680.o: bme680.c
bsec_integration.o: bsec_integration.c
bsec_serialized_configurations_iaq.o: bsec_serialized_configurations_iaq.c

clean:
	rm -f *.o reader
