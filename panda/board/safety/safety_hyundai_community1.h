#include "safety_hyundai_common.h"

const CanMsg HYUNDAI_COMMUNITY1_TX_MSGS[] = {
  {0x340, 0, 8},  // LKAS11 Bus 0
  {0x4F1, 0, 4}, // CLU11 Bus 0
  {0x485, 0, 4}, // LFAHDA_MFC Bus 0
  {0x4F1, 2, 4}, // CLU11 Bus 2
  {0x251, 2, 8},  // MDPS12 Bus 2
  {0x420, 0, 8}, // SCC11 Bus 0
  {0x421, 0, 8}, // SCC12 Bus 0
  {0x50A, 0, 8}, // SCC13 Bus 0
  {0x389, 0, 8},  // SCC14 Bus 0
  {0x38D, 0, 8},  // FCA11 Bus 0
  {0x483, 0, 8}, // FCA12 Bus 0
  {0x4A2, 0, 8}, // FRT_RADAR11 Bus 0
};

const CanMsg HYUNDAI_COMMUNITY1_LONG_TX_MSGS[] = {
  {0x340, 0, 8},  // LKAS11 Bus 0
  {0x4F1, 0, 4}, // CLU11 Bus 0
  {0x485, 0, 4}, // LFAHDA_MFC Bus 0
  {0x420, 0, 8}, // SCC11 Bus 0
  {0x421, 0, 8}, // SCC12 Bus 0
  {0x50A, 0, 8}, // SCC13 Bus 0
  {0x389, 0, 8},  // SCC14 Bus 0
  {0x4A2, 0, 2}, // FRT_RADAR11 Bus 0
  {0x38D, 0, 8},  // FCA11 Bus 0
  {0x483, 0, 8}, // FCA12 Bus 0
  {0x7D0, 0, 8}, // radar UDS TX addr Bus 0 (for radar disable)
  {0x4F1, 2, 4}, // CLU11 Bus 2
  {0x251, 2, 8},  // MDPS12 Bus 2
};

const CanMsg HYUNDAI_COMMUNITY1_CAMERA_SCC_TX_MSGS[] = {
  {0x340, 0, 8},  // LKAS11 Bus 0
  {0x4F1, 2, 4}, // CLU11 Bus 2
  {0x485, 0, 4}, // LFAHDA_MFC Bus 0
  {0x251, 2, 8},  // MDPS12 Bus 2
  {0x4F1, 0, 4}, // CLU11 Bus 0
  {0x420, 0, 8}, // SCC11 Bus 0
  {0x421, 0, 8}, // SCC12 Bus 0
  {0x50A, 0, 8}, // SCC13 Bus 0
  {0x389, 0, 8},  // SCC14 Bus 0
  {0x38D, 0, 8},  // FCA11 Bus 0
  {0x483, 0, 8}, // FCA12 Bus 0
  {0x4A2, 0, 8}, // FRT_RADAR11 Bus 0
};

AddrCheckStruct hyundai_community1_addr_checks[] = {
  {.msg = {{0x260, 0, 8, .check_checksum = true, .max_counter = 3U, .expected_timestep = 10000U},
           {0x371, 0, 8, .expected_timestep = 10000U}, { 0 }}},
  {.msg = {{0x386, 0, 8, .check_checksum = true, .max_counter = 15U, .expected_timestep = 10000U}, { 0 }, { 0 }}},
  {.msg = {{0x394, 0, 8, .check_checksum = true, .max_counter = 7U, .expected_timestep = 10000U}, { 0 }, { 0 }}},
  {.msg = {{0x421, 0, 8, .check_checksum = true, .max_counter = 15U, .expected_timestep = 20000U}, { 0 }, { 0 }}},
};
#define HYUNDAI_COMMUNITY1_ADDR_CHECK_LEN (sizeof(hyundai_community1_addr_checks) / sizeof(hyundai_community1_addr_checks[0]))

AddrCheckStruct hyundai_community1_cam_scc_addr_checks[] = {
  {.msg = {{0x260, 0, 8, .check_checksum = true, .max_counter = 3U, .expected_timestep = 10000U},
           {0x371, 0, 8, .expected_timestep = 10000U}, { 0 }}},
  {.msg = {{0x386, 0, 8, .check_checksum = true, .max_counter = 15U, .expected_timestep = 10000U}, { 0 }, { 0 }}},
  {.msg = {{0x394, 0, 8, .check_checksum = true, .max_counter = 7U, .expected_timestep = 10000U}, { 0 }, { 0 }}},
  {.msg = {{0x421, 2, 8, .check_checksum = true, .max_counter = 15U, .expected_timestep = 20000U}, { 0 }, { 0 }}},
};
#define HYUNDAI_COMMUNITY1_CAM_SCC_ADDR_CHECK_LEN (sizeof(hyundai_community1_cam_scc_addr_checks) / sizeof(hyundai_community1_cam_scc_addr_checks[0]))

AddrCheckStruct hyundai_community1_long_addr_checks[] = {
  {.msg = {{0x260, 0, 8, .check_checksum = true, .max_counter = 3U, .expected_timestep = 10000U},
           {0x371, 0, 8, .expected_timestep = 10000U}, { 0 }}},
  {.msg = {{0x386, 0, 8, .check_checksum = true, .max_counter = 15U, .expected_timestep = 10000U}, { 0 }, { 0 }}},
  {.msg = {{0x394, 0, 8, .check_checksum = true, .max_counter = 7U, .expected_timestep = 10000U}, { 0 }, { 0 }}},
  {.msg = {{0x4F1, 0, 4, .check_checksum = false, .max_counter = 15U, .expected_timestep = 20000U}, { 0 }, { 0 }}},
};
#define HYUNDAI_COMMUNITY1_LONG_ADDR_CHECK_LEN (sizeof(hyundai_community1_long_addr_checks) / sizeof(hyundai_community1_long_addr_checks[0]))

// older hyundai models have less checks due to missing counters and checksums
AddrCheckStruct hyundai_community1_legacy_addr_checks[] = {
  {.msg = {{0x260, 0, 8, .check_checksum = true, .max_counter = 3U, .expected_timestep = 10000U},
           {0x371, 0, 8, .expected_timestep = 10000U}, { 0 }}},
  {.msg = {{0x386, 0, 8, .expected_timestep = 20000U}, { 0 }, { 0 }}},
  //{.msg = {{0x394, 0, 8, .expected_timestep = 10000U}, { 0 }, { 0 }}},
  //{.msg = {{0x421, 0, 8, .check_checksum = true, .max_counter = 15U, .expected_timestep = 20000U}, { 0 }, { 0 }}},
};
#define HYUNDAI_COMMUNITY1_LEGACY_ADDR_CHECK_LEN (sizeof(hyundai_community1_legacy_addr_checks) / sizeof(hyundai_community1_legacy_addr_checks[0]))

bool hyundai_community1_legacy = false;

addr_checks hyundai_community1_rx_checks = {hyundai_community1_addr_checks, HYUNDAI_COMMUNITY1_ADDR_CHECK_LEN};

static int hyundai_community1_rx_hook(CANPacket_t *to_push) {

  bool valid = addr_safety_check(to_push, &hyundai_community1_rx_checks,
                                 hyundai_get_checksum, hyundai_compute_checksum,
                                 hyundai_get_counter, NULL);

  int bus = GET_BUS(to_push);
  int addr = GET_ADDR(to_push);

  //// SCC12 is on bus 2 for camera-based SCC cars, bus 0 on all others
  //if (valid && (addr == 0x421) && (((bus == 0) && !hyundai_camera_scc) || ((bus == 2) && hyundai_camera_scc))) {
  //  // 2 bits: 13-14
  //  int cruise_engaged = (GET_BYTES(to_push, 0, 4) >> 13) & 0x3U;
  //  hyundai_common_cruise_state_check(cruise_engaged);
  //}

  // MainMode ACC
  if (valid && (addr == 0x420)) {
    // 1 bits: 0
    int cruise_available = GET_BIT(to_push, 0U);
    hyundai_common_cruise_state_check_alt(cruise_available);
  }

  if (valid && (bus == 0)) {
    if (addr == 0x251) {
      int torque_driver_new = ((GET_BYTES(to_push, 0, 4) & 0x7ffU) * 0.79) - 808; // scale down new driver torque signal to match previous one
      // update array of samples
      update_sample(&torque_driver, torque_driver_new);
    }

    // ACC steering wheel buttons
    if (addr == 0x4F1) {
      int cruise_button = GET_BYTE(to_push, 0) & 0x7U;
      int main_button = GET_BIT(to_push, 3U);
      hyundai_common_cruise_buttons_check(cruise_button, main_button);
    }

    // gas press, different for EV, hybrid, and ICE models
    if ((addr == 0x371) && hyundai_ev_gas_signal) {
      gas_pressed = (((GET_BYTE(to_push, 4) & 0x7FU) << 1) | GET_BYTE(to_push, 3) >> 7) != 0U;
    } else if ((addr == 0x371) && hyundai_hybrid_gas_signal) {
      gas_pressed = GET_BYTE(to_push, 7) != 0U;
    } else if ((addr == 0x260) && !hyundai_ev_gas_signal && !hyundai_hybrid_gas_signal) {
      gas_pressed = (GET_BYTE(to_push, 7) >> 6) != 0U;
    } else {
    }

    // sample wheel speed, averaging opposite corners
    if (addr == 0x386) {
      uint32_t front_left_speed = GET_BYTES(to_push, 0, 2) & 0x3FFFU;
      uint32_t rear_right_speed = GET_BYTES(to_push, 6, 2) & 0x3FFFU;
      vehicle_moving = (front_left_speed > HYUNDAI_STANDSTILL_THRSLD) || (rear_right_speed > HYUNDAI_STANDSTILL_THRSLD);
    }

    if (addr == 0x394) {
      brake_pressed = GET_BIT(to_push, 55U) != 0U;
    }
    gas_pressed = brake_pressed = false;
    bool stock_ecu_detected = (addr == 0x340);

    // If openpilot is controlling longitudinal we need to ensure the radar is turned off
    // Enforce by checking we don't see SCC12
    if (hyundai_longitudinal && (addr == 0x421)) {
      stock_ecu_detected = true;
    }
    generic_rx_checks(stock_ecu_detected);
  }
  return valid;
}

uint32_t last_ts_lkas11_from_op = 0;
uint32_t last_ts_scc12_from_op = 0;
uint32_t last_ts_mdps12_from_op = 0;
uint32_t last_ts_fca11_from_op = 0;

static int hyundai_community1_tx_hook(CANPacket_t *to_send) {

  int tx = 1;
  int addr = GET_ADDR(to_send);

  if (hyundai_longitudinal) {
    tx = msg_allowed(to_send, HYUNDAI_COMMUNITY1_LONG_TX_MSGS, sizeof(HYUNDAI_COMMUNITY1_LONG_TX_MSGS)/sizeof(HYUNDAI_COMMUNITY1_LONG_TX_MSGS[0]));
  } else if (hyundai_camera_scc) {
    tx = msg_allowed(to_send, HYUNDAI_COMMUNITY1_CAMERA_SCC_TX_MSGS, sizeof(HYUNDAI_COMMUNITY1_CAMERA_SCC_TX_MSGS)/sizeof(HYUNDAI_COMMUNITY1_CAMERA_SCC_TX_MSGS[0]));
  } else {
    tx = msg_allowed(to_send, HYUNDAI_COMMUNITY1_TX_MSGS, sizeof(HYUNDAI_COMMUNITY1_TX_MSGS)/sizeof(HYUNDAI_COMMUNITY1_TX_MSGS[0]));
  }

  // FCA11: Block any potential actuation
  if (addr == 0x38D) {
    int CR_VSM_DecCmd = GET_BYTE(to_send, 1);
    int FCA_CmdAct = GET_BIT(to_send, 20U);
    int CF_VSM_DecCmdAct = GET_BIT(to_send, 31U);

    if ((CR_VSM_DecCmd != 0) || (FCA_CmdAct != 0) || (CF_VSM_DecCmdAct != 0)) {
      tx = 0;
    }
  }

  // ACCEL: safety check
  if (addr == 0x421) {
    int desired_accel_raw = (((GET_BYTE(to_send, 4) & 0x7U) << 8) | GET_BYTE(to_send, 3)) - 1023U;
    int desired_accel_val = ((GET_BYTE(to_send, 5) << 3) | (GET_BYTE(to_send, 4) >> 5)) - 1023U;

    //int aeb_decel_cmd = GET_BYTE(to_send, 2);
    //int aeb_req = GET_BIT(to_send, 54U);

    bool violation = false;

    violation |= longitudinal_accel_checks(desired_accel_raw, HYUNDAI_LONG_LIMITS);
    violation |= longitudinal_accel_checks(desired_accel_val, HYUNDAI_LONG_LIMITS);
    //violation |= (aeb_decel_cmd != 0);
    //violation |= (aeb_req != 0);

    if (violation) {
      tx = 0;
    }
  }

  // LKA STEER: safety check
  if (addr == 0x340) {
    int desired_torque = ((GET_BYTES(to_send, 0, 4) >> 16) & 0x7ffU) - 1024U;
    bool steer_req = GET_BIT(to_send, 27U) != 0U;

    const SteeringLimits limits = hyundai_alt_limits ? HYUNDAI_STEERING_LIMITS_ALT : HYUNDAI_STEERING_LIMITS;
    if (steer_torque_cmd_checks(desired_torque, steer_req, limits)) {
      tx = 0;
    }
  }

  // UDS: Only tester present ("\x02\x3E\x80\x00\x00\x00\x00\x00") allowed on diagnostics address
  if (addr == 0x7D0) {
    if ((GET_BYTES(to_send, 0, 4) != 0x00803E02U) || (GET_BYTES(to_send, 4, 4) != 0x0U)) {
      tx = 0;
    }
  }

  //// BUTTONS: used for resume spamming and cruise cancellation
  //if ((addr == 0x4F1) && !hyundai_longitudinal) {
  //  int button = GET_BYTE(to_send, 0) & 0x7U;
  //
  //  bool allowed_resume = (button == 1) && controls_allowed;
  //
  //  bool allowed_cancel = (button == 4) && cruise_engaged_prev;
  //  if (!(allowed_resume || allowed_cancel)) {
  //    tx = 0;
  //  }
  //}

  if (addr == 0x340) {
    last_ts_lkas11_from_op = (tx == 0 ? 0 : microsecond_timer_get());
  } else if (addr == 0x421) {
    last_ts_scc12_from_op = (tx == 0 ? 0 : microsecond_timer_get());
  } else if (addr == 0x251) {
    last_ts_mdps12_from_op = (tx == 0 ? 0 : microsecond_timer_get());
  } else if (addr == 0x38D) {
    last_ts_fca11_from_op = (tx == 0 ? 0 : microsecond_timer_get());
  }

  return tx;
}

static int hyundai_community1_fwd_hook(int bus_num, int addr) {

  int bus_fwd = -1;

  uint32_t now = microsecond_timer_get();

  // forward cam to ccan and viceversa, except lkas cmd
  if (bus_num == 0) {
    bus_fwd = 2;

    if(addr == 0x251) {
      if(now - last_ts_mdps12_from_op < 200000) {
        bus_fwd = -1;
      }
    }
  }

  if (bus_num == 2) {
    bool is_lkas_msg = addr == 0x340;
    bool is_lfahda_msg = addr == 0x485;
    bool is_scc_msg = addr == 0x420 || addr == 0x421 || addr == 0x50A || addr == 0x389;
    bool is_fca_msg = addr == 0x38D || addr == 0x483;

    bool block_msg = is_lkas_msg || is_lfahda_msg || is_scc_msg; //|| is_fca_msg;
    if (!block_msg) {
      bus_fwd = 0;
    }
    else {
      if(is_lkas_msg || is_lfahda_msg) {
        if(now - last_ts_lkas11_from_op >= 200000) {
          bus_fwd = 0;
        }
      }
      else if(is_scc_msg) {
        if(now - last_ts_scc12_from_op >= 400000)
          bus_fwd = 0;
      }
      else if(is_fca_msg) {
        if(now - last_ts_fca11_from_op >= 400000)
          bus_fwd = 0;
      }
    }
  }

  return bus_fwd;
}

static const addr_checks* hyundai_community1_init(uint16_t param) {
  hyundai_common_init(param);
  hyundai_community1_legacy = false;

  if (hyundai_camera_scc) {
    hyundai_longitudinal = false;
  }

  if (hyundai_longitudinal) {
    hyundai_community1_rx_checks = (addr_checks){hyundai_community1_long_addr_checks, HYUNDAI_COMMUNITY1_LONG_ADDR_CHECK_LEN};
  } else if (hyundai_camera_scc) {
    hyundai_community1_rx_checks = (addr_checks){hyundai_community1_cam_scc_addr_checks, HYUNDAI_COMMUNITY1_CAM_SCC_ADDR_CHECK_LEN};
  } else {
    hyundai_community1_rx_checks = (addr_checks){hyundai_community1_addr_checks, HYUNDAI_COMMUNITY1_ADDR_CHECK_LEN};
  }
  return &hyundai_community1_rx_checks;
}

static const addr_checks* hyundai_community1_legacy_init(uint16_t param) {
  hyundai_common_init(param);
  hyundai_community1_legacy = true;
  hyundai_longitudinal = false;
  hyundai_camera_scc = false;

  hyundai_community1_rx_checks = (addr_checks){hyundai_community1_legacy_addr_checks, HYUNDAI_COMMUNITY1_LEGACY_ADDR_CHECK_LEN};
  return &hyundai_community1_rx_checks;
}

const safety_hooks hyundai_community1_hooks = {
  .init = hyundai_community1_init,
  .rx = hyundai_community1_rx_hook,
  .tx = hyundai_community1_tx_hook,
  .tx_lin = nooutput_tx_lin_hook,
  .fwd = hyundai_community1_fwd_hook,
};

const safety_hooks hyundai_community1_legacy_hooks = {
  .init = hyundai_community1_legacy_init,
  .rx = hyundai_community1_rx_hook,
  .tx = hyundai_community1_tx_hook,
  .tx_lin = nooutput_tx_lin_hook,
  .fwd = hyundai_community1_fwd_hook,
};
