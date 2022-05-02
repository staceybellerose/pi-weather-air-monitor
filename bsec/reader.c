/*
 * Copyright 2017 Robert Bosch, 2022 Stacey Adams. All Rights Reserved.
 */

/*!
 * @file bsec_iot_example.c
 *
 * @brief
 * Example for using of BSEC library in a fixed configuration with the BME680 sensor.
 * This works by running an endless loop in the bsec_iot_loop() function.
 */

/*!
 * @addtogroup bsec_examples BSEC Examples
 * @brief BSEC usage examples
 * @{*/

/**********************************************************************************************************************/
/* header files */
/**********************************************************************************************************************/

#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <math.h>
#include <linux/i2c-dev.h>
#include <fcntl.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <sys/time.h>
#include <unistd.h>
#include "bsec_integration.h"
#include "bsec_serialized_configurations_iaq.h"

// I2C Linux device handle
int g_i2cFid;

// open the Linux device
void i2cOpen()
{
	g_i2cFid = open("/dev/i2c-1", O_RDWR);
	if (g_i2cFid < 0) {
		perror("i2cOpen");
		exit(1);
	}
}

// close the Linux device
void i2cClose()
{
	close(g_i2cFid);
}

// set the I2C slave address for all subsequent I2C device transfers
void i2cSetAddress(int address)
{
	if (ioctl(g_i2cFid, I2C_SLAVE, address) < 0) {
		perror("i2cSetAddress");
		exit(1);
	}
}

/**********************************************************************************************************************/
/* functions */
/**********************************************************************************************************************/

/*!
 * @brief           Write operation in either I2C or SPI
 *
 * param[in]        dev_addr        I2C or SPI device address
 * param[in]        reg_addr        register address
 * param[in]        reg_data_ptr    pointer to the data to be written
 * param[in]        data_len        number of bytes to be written
 *
 * @return          result of the bus communication function
 */
int8_t bus_write(uint8_t dev_addr, uint8_t reg_addr, uint8_t *reg_data_ptr, uint16_t data_len)
{
    int8_t rslt = 0; /* Return 0 for Success, non-zero for failure */

	uint8_t reg[16];
    reg[0]=reg_addr;

    for (int i=1; i<data_len+1; i++) {
        reg[i] = reg_data_ptr[i-1];
    }
    if (write(g_i2cFid, reg, data_len+1) != data_len+1) {
		perror("user_i2c_write");
		rslt = 1;
        exit(1);
	}

    return rslt;
}

/*!
 * @brief           Read operation in either I2C or SPI
 *
 * param[in]        dev_addr        I2C or SPI device address
 * param[in]        reg_addr        register address
 * param[out]       reg_data_ptr    pointer to the memory to be used to store the read data
 * param[in]        data_len        number of bytes to be read
 *
 * @return          result of the bus communication function
 */
int8_t bus_read(uint8_t dev_addr, uint8_t reg_addr, uint8_t *reg_data_ptr, uint16_t data_len)
{
    int8_t rslt = 0; /* Return 0 for Success, non-zero for failure */

    uint8_t reg[1];
	reg[0]=reg_addr;

    if (write(g_i2cFid, reg, 1) != 1) {
		perror("user_i2c_read_reg");
		rslt = 1;
	}
	if (read(g_i2cFid, reg_data_ptr, data_len) != data_len) {
		perror("user_i2c_read_data");
		rslt = 1;
	}

    return rslt;
}

/*!
 * @brief           System specific implementation of sleep function
 *
 * @param[in]       t_ms    time in milliseconds
 *
 * @return          none
 */
void sleeper(uint32_t t_ms)
{
    usleep(t_ms * 1000);
}

/*!
 * @brief           Capture the system time in microseconds
 *
 * @return          system_current_time    current system timestamp in microseconds
 */
int64_t get_timestamp_us()
{
    struct timeval tv;
    gettimeofday(&tv, NULL);
    int64_t system_current_time = tv.tv_sec * 1000000ll + tv.tv_usec;

    return system_current_time;
}

/*!
 * @brief           Handling of the ready outputs
 *
 * @param[in]       timestamp       time in nanoseconds
 * @param[in]       iaq             IAQ signal
 * @param[in]       iaq_accuracy    accuracy of IAQ signal
 * @param[in]       temperature     temperature signal
 * @param[in]       humidity        humidity signal
 * @param[in]       pressure        pressure signal
 * @param[in]       raw_temperature raw temperature signal
 * @param[in]       raw_humidity    raw humidity signal
 * @param[in]       gas             raw gas sensor signal
 * @param[in]       bsec_status     value returned by the bsec_do_steps() call
 *
 * @return          none
 */
void output_ready(int64_t timestamp, float iaq, uint8_t iaq_accuracy, float temperature, float humidity,
    float pressure, float raw_temperature, float raw_humidity, float gas, bsec_library_return_t bsec_status,
    float static_iaq, float co2_equivalent, float breath_voc_equivalent)
{
    #ifdef DEBUG
        printf("[%.3lf] ", timestamp/1000000000.0d);
        printf("T: %.1f°C, P: %.1f hPa, rH: %.1f%%, ", temperature, pressure / 100.0f, humidity);
        printf("G: %.0f Ω, IAQ: %.1f", gas, iaq);
    #else
        printf("%.3lf|", timestamp/1000000000.0d);
        printf("%.1f|%.1f|%.1f%%|", temperature, pressure / 100.0f, humidity);
        printf("%.0f|%.1f", gas, iaq);
    #endif
    printf("\n");
}

void output_header()
{
    printf("Timestamp|Temperature|Pressure|RelativeHumidity|GasRawReading|IAQ\n");
}

char* STATE_FILE_PATH = "bsec_state.dat";

/*!
 * @brief           Load previous library state from non-volatile memory
 *
 * @param[in,out]   state_buffer    buffer to hold the loaded state string
 * @param[in]       n_buffer        size of the allocated state buffer
 *
 * @return          number of bytes copied to state_buffer
 */
uint32_t state_load(uint8_t *state_buffer, uint32_t n_buffer)
{
    // ...
    // Load a previous library state from non-volatile memory, if available.
    //
    // Return zero if loading was unsuccessful or no state was available,
    // otherwise return length of loaded state string.
    // ...
    FILE* state_file;
    uint32_t size;

    // Make sure the file exists, by opening it in append mode and immediately closing it
    state_file = fopen(STATE_FILE_PATH, "a");
    fclose(state_file);

    state_file = fopen(STATE_FILE_PATH, "r");
    if (state_file) {
        size = fread(state_buffer, 1, n_buffer, state_file);
        fprintf(stderr, "Loaded sensor state (%d bytes)\n", size);
    } else {
        size = 0;
    }
    fclose(state_file);
    return size;
}

/*!
 * @brief           Save library state to non-volatile memory
 *
 * @param[in]       state_buffer    buffer holding the state to be stored
 * @param[in]       length          length of the state string to be stored
 *
 * @return          none
 */
void state_save(const uint8_t *state_buffer, uint32_t length)
{
    // ...
    // Save the string some form of non-volatile memory, if possible.
    // ...
    FILE* state_file;

    state_file = fopen(STATE_FILE_PATH, "w");
    if (state_file) {
        fwrite(state_buffer, 1, length, state_file);
        fprintf(stderr, "Saved sensor state\n");
    } else {
        fprintf(stderr, "Unable to save sensor state!\n");
    }
    fclose(state_file);
}

/*!
 * @brief           Load library config from non-volatile memory
 *
 * @param[in,out]   config_buffer    buffer to hold the loaded state string
 * @param[in]       n_buffer        size of the allocated state buffer
 *
 * @return          number of bytes copied to config_buffer
 */
uint32_t config_load(uint8_t *config_buffer, uint32_t n_buffer)
{
    // ...
    // Load a library config from non-volatile memory, if available.
    //
    // Return zero if loading was unsuccessful or no config was available,
    // otherwise return length of loaded config string.
    // ...
    memcpy(config_buffer, bsec_config_iaq, sizeof(bsec_config_iaq));
    return sizeof(bsec_config_iaq);
}

/*!
 * @brief       Main function which configures BSEC library and then reads and processes the data from sensor based
 *              on timer ticks
 *
 * @return      result of the processing
 */
int main()
{
    return_values_init ret;

    setbuf(stdout, NULL);

    fprintf(stderr, "Starting sensor reader...\n");

    i2cOpen();
    i2cSetAddress(BME680_I2C_ADDR_SECONDARY);

    fprintf(stderr, "I2C initialized...\n");

    /* Call to the function which initializes the BSEC library
     * Switch on continuous mode and provide no temperature offset */
    ret = bsec_iot_init(BSEC_SAMPLE_RATE_CONTINUOUS, 0.0f, bus_write, bus_read, sleeper, state_load, config_load);
    if (ret.bme680_status)
    {
        /* Could not intialize BME680 */
        return (int)ret.bme680_status;
    }
    else if (ret.bsec_status)
    {
        /* Could not intialize BSEC library */
        return (int)ret.bsec_status;
    }

    fprintf(stderr, "BSEC initialized...\n");

    #ifndef DEBUG
        output_header();
    #endif

    /* Call to endless loop function which reads and processes data based on sensor settings */
    /* State is saved every 3600 samples, which means every 3600 * 1 secs = 60 minutes  */
    bsec_iot_loop(sleeper, get_timestamp_us, output_ready, state_save, 3600);

    return 0;
}

/*! @}*/

