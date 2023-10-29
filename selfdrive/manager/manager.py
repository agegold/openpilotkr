#!/usr/bin/env python3
import datetime
import os
import signal
import subprocess
import sys
import traceback
from typing import List, Tuple, Union

from cereal import log
import cereal.messaging as messaging
import openpilot.selfdrive.sentry as sentry
from openpilot.common.basedir import BASEDIR, PYEXTRADIR
from openpilot.common.params import Params, ParamKeyType
from openpilot.common.text_window import TextWindow
from openpilot.selfdrive.boardd.set_time import set_time
from openpilot.system.hardware import HARDWARE, PC
from openpilot.selfdrive.manager.helpers import unblock_stdout, write_onroad_params
from openpilot.selfdrive.manager.process import ensure_running
from openpilot.selfdrive.manager.process_config import managed_processes
from openpilot.selfdrive.athena.registration import register, UNREGISTERED_DONGLE_ID
from openpilot.system.swaglog import cloudlog, add_file_handler
from openpilot.system.version import is_dirty, get_commit, get_version, get_origin, get_short_branch, \
                           get_normalized_origin, terms_version, training_version, \
                           is_tested_branch, is_release_branch


sys.path.append(os.path.join(PYEXTRADIR, "pyextra"))


def manager_init() -> None:
  # update system time from panda
  set_time(cloudlog)

  # save boot log
  #subprocess.call("./bootlog", cwd=os.path.join(BASEDIR, "system/loggerd"))

  params = Params()
  params.clear_all(ParamKeyType.CLEAR_ON_MANAGER_START)
  params.clear_all(ParamKeyType.CLEAR_ON_ONROAD_TRANSITION)
  params.clear_all(ParamKeyType.CLEAR_ON_OFFROAD_TRANSITION)

  default_params: List[Tuple[str, Union[str, bytes]]] = [
    ("CompletedTrainingVersion", "0"),
    ("DisengageOnAccelerator", "0"),
    ("GsmMetered", "1"),
    ("HasAcceptedTerms", "0"),
    ("LanguageSetting", "main_en"),
    ("OpenpilotEnabledToggle", "1"),
    ("LongitudinalPersonality", str(log.LongitudinalPersonality.standard)),
    ("IsMetric", "1"),
    ("IsOpenpilotViewEnabled", "0"),
    ("OpkrAutoShutdown", "12"),
    ("OpkrForceShutdown", "5"),
    ("OpkrAutoScreenOff", "-2"),
    ("OpkrUIBrightness", "0"),
    ("OpkrUIVolumeBoost", "0"),
    ("OpkrEnableDriverMonitoring", "1"),
    ("OpkrEnableLogger", "0"),
    ("OpkrEnableUploader", "0"),
    ("OpkrEnableGetoffAlert", "0"),
    ("OpkrAutoResume", "1"),
    ("OpkrVariableCruise", "1"),
    ("OpkrLaneChangeSpeed", "20"),
    ("OpkrAutoLaneChangeDelay", "0"),
    ("OpkrSteerAngleCorrection", "0"),
    ("PutPrebuiltOn", "0"),
    ("LdwsCarFix", "0"),
    ("LateralControlMethod", "3"),
    ("CruiseStatemodeSelInit", "1"),
    ("InnerLoopGain", "35"),
    ("OuterLoopGain", "20"),
    ("TimeConstant", "14"),
    ("ActuatorEffectiveness", "20"),
    ("Scale", "1500"),
    ("LqrKi", "16"),
    ("DcGain", "265"),
    ("PidKp", "25"),
    ("PidKi", "40"),
    ("PidKd", "150"),
    ("PidKf", "7"),
    ("TorqueKp", "10"),
    ("TorqueKf", "10"),
    ("TorqueKi", "1"),
    ("TorqueFriction", "80"),
    ("TorqueUseAngle", "1"),
    ("TorqueMaxLatAccel", "30"),
    ("TorqueAngDeadZone", "10"),
    ("CameraOffsetAdj", "40"),
    ("PathOffsetAdj", "0"),
    ("SteerRatioAdj", "1375"),
    ("SteerRatioMaxAdj", "1750"),
    ("SteerActuatorDelayAdj", "36"),
    ("SteerLimitTimerAdj", "100"),
    ("TireStiffnessFactorAdj", "85"),
    ("SteerMaxBaseAdj", "384"),
    ("SteerMaxAdj", "384"),
    ("SteerDeltaUpBaseAdj", "3"),
    ("SteerDeltaUpAdj", "3"),
    ("SteerDeltaDownBaseAdj", "7"),
    ("SteerDeltaDownAdj", "7"),
    ("LeftCurvOffsetAdj", "0"),
    ("RightCurvOffsetAdj", "0"),
    ("DebugUi1", "0"),
    ("DebugUi2", "0"),
    ("DebugUi3", "0"),
    ("LongLogDisplay", "0"),
    ("OpkrBlindSpotDetect", "1"),
    ("OpkrMaxAngleLimit", "80"),
    ("OpkrSteerMethod", "0"),
    ("OpkrMaxSteeringAngle", "90"),
    ("OpkrMaxDriverAngleWait", "0.002"),
    ("OpkrMaxSteerAngleWait", "0.001"),
    ("OpkrDriverAngleWait", "0.001"),
    ("OpkrSpeedLimitOffset", "0"),
    ("OpkrLiveSteerRatio", "1"),
    ("OpkrVariableSteerMax", "0"),
    ("OpkrVariableSteerDelta", "0"),
    ("FingerprintTwoSet", "0"),
    ("OpkrDrivingRecord", "0"),
    ("OpkrTurnSteeringDisable", "0"),
    ("CarModel", ""),
    ("OpkrHotspotOnBoot", "0"),
    ("OpkrSSHLegacy", "1"),
    ("CruiseOverMaxSpeed", "0"),
    ("JustDoGearD", "0"),
    ("LanelessMode", "2"),
    ("ComIssueGone", "1"),
    ("MaxSteer", "384"),
    ("MaxRTDelta", "112"),
    ("MaxRateUp", "3"),
    ("MaxRateDown", "7"),
    ("SteerThreshold", "150"),
    ("RecordingCount", "200"),
    ("RecordingQuality", "1"),
    ("CruiseGapAdjust", "0"),
    ("AutoEnable", "0"),
    ("CruiseAutoRes", "0"),
    ("AutoResOption", "0"),
    ("AutoResCondition", "0"),
    ("OpkrMonitoringMode", "0"),
    ("OpkrMonitorEyesThreshold", "45"),
    ("OpkrMonitorNormalEyesThreshold", "45"),
    ("OpkrMonitorBlinkThreshold", "35"),
    ("UFCModeEnabled", "0"),
    ("SteerWarningFix", "0"),
    ("CruiseGap1", "11"),
    ("CruiseGap2", "12"),
    ("CruiseGap3", "13"),
    ("CruiseGap4", "15"),
    ("DynamicTRGap", "1"),
    ("DynamicTRSpd", "0,20,40,60,110"),
    ("DynamicTRSet", "1.1,1.2,1.3,1.4,1.5"),
    ("LCTimingFactorUD", "1"),
    ("LCTimingFactor30", "30"),
    ("LCTimingFactor60", "60"),
    ("LCTimingFactor80", "80"),
    ("LCTimingFactor110", "100"),
    ("OpkrUIBrightnessOff", "10"),
    ("LCTimingFactorEnable", "0"),
    ("AutoEnableSpeed", "5"),
    ("SafetyCamDecelDistGain", "0"),
    ("OpkrLiveTunePanelEnable", "0"),
    ("RadarLongHelper", "2"),
    ("GitPullOnBoot", "0"),
    ("LiveSteerRatioPercent", "0"),
    ("StoppingDistAdj", "0"),
    ("ShowError", "1"),
    ("AutoResLimitTime", "0"),
    ("VCurvSpeedC", "30,50,70,90"),
    ("VCurvSpeedT", "43,58,73,87"),
    ("VCurvSpeedCMPH", "20,30,45,60"),
    ("VCurvSpeedTMPH", "27,36,46,57"),
    ("OCurvSpeedC", "30,40,50,60,70"),
    ("OCurvSpeedT", "35,45,60,70,80"),
    ("OSMCustomSpeedLimitC", "30,40,50,60,70,90"),
    ("OSMCustomSpeedLimitT", "30,40,65,72,80,95"),
    ("StockNaviSpeedEnabled", "0"),
    ("OPKRNaviSelect", "0"),
    ("E2ELong", "0"),
    ("OPKRServer", "0"),
    ("OPKRMapboxStyleSelect", "0"),
    ("IgnoreCANErroronISG", "0"),
    ("RESCountatStandstill", "18"),
    ("OpkrSpeedLimitOffsetOption", "0"),
    ("OpkrSpeedLimitSignType", "0"),
    ("StockLKASEnabled", "0"),
    ("SpeedLimitDecelOff", "0"),
    ("CurvDecelOption", "2"),
    ("FCA11Message", "0"),
    ("StandstillResumeAlt", "0"),
    ("AutoRESDelay", "1"),
    ("UseRadarTrack", "0"),
    ("RadarDisable", "0"),
    ("DesiredCurvatureLimit", "10"),
    ("CustomTREnabled", "1"),
    ("RoadList", "RoadName1,+0.0,RoadName2,-0.0\nRoadName3,30,RoadName4,60"),
    ("LaneWidth", "37"),
    ("SpdLaneWidthSpd", "0,31"),
    ("SpdLaneWidthSet", "2.8,3.5"),
    ("BottomTextView", "0"),
    ("CloseToRoadEdge", "0"),
    ("LeftEdgeOffset", "0"),
    ("RightEdgeOffset", "0"),
    ("AvoidLKASFaultEnabled", "1"),
    ("AvoidLKASFaultMaxAngle", "85"),
    ("AvoidLKASFaultMaxFrame", "89"),
    ("AvoidLKASFaultBeyond", "0"),
    ("UseStockDecelOnSS", "0"),
    ("AnimatedRPM", "1"),
    ("AnimatedRPMMax", "3600"),
    ("RoutineDriveOption", "OPKR"),
    ("SshEnabled", "1"),
    ("UserSpecificFeature", "0"),
    ("OpkrWakeUp", "0"),
    ("MultipleLateralUse", "2"),
    ("MultipleLateralOpS", "3,3,0"),
    ("MultipleLateralSpd", "60,90"),
    ("MultipleLateralOpA", "3,3,0"),
    ("MultipleLateralAng", "20,35"),
    ("StoppingDist", "35"),
    ("StopAtStopSign", "0"),
    ("VarCruiseSpeedFactor", "15"),
    ("OPKRSpeedBump", "0"),
    ("OPKREarlyStop", "1"),
    ("DoNotDisturbMode", "0"),
    ("DepartChimeAtResume", "0"),
    ("CommaStockUI", "0"),
    ("CruiseGapBySpdOn", "0"),
    ("CruiseGapBySpdSpd", "25,55,130"),
    ("CruiseGapBySpdGap", "1,2,3,4"),
    ("CruiseSetwithRoadLimitSpeedEnabled", "0"),
    ("CruiseSetwithRoadLimitSpeedOffset", "0"),
    ("OpkrLiveTorque", "1"),
    ("ExternalDeviceIP", ""),
    ("ExternalDeviceIPNow", ""),
    ("SetSpeedFive", "0"),
    ("OPKRLongAlt", "0"),
    ("LowUIProfile", "0"),
    ("NavHome", ""),
    ("NavWork", ""),
    ("NavList", ""),
    ("MapboxToken", ""),
    ("RunCustomCommand", "0"),
    ("CruiseSpammingSpd", "50,80,110"),
    ("CruiseSpammingLevel", "15,10,5,0"),
    ("OpkrCruiseGapSet", "4"),
  ]
  if not PC:
    default_params.append(("LastUpdateTime", datetime.datetime.utcnow().isoformat().encode('utf8')))

  if params.get_bool("RecordFrontLock"):
    params.put_bool("RecordFront", True)

  # set unset params
  for k, v in default_params:
    if params.get(k) is None:
      params.put(k, v)

  # is this dashcam?
  if os.getenv("PASSIVE") is not None:
    params.put_bool("Passive", bool(int(os.getenv("PASSIVE", "0"))))

  if params.get("Passive") is None:
    raise Exception("Passive must be set to continue")

  # Create folders needed for msgq
  try:
    os.mkdir("/dev/shm")
  except FileExistsError:
    pass
  except PermissionError:
    print("WARNING: failed to make /dev/shm")

  # set version params
  params.put("Version", get_version())
  params.put("TermsVersion", terms_version)
  params.put("TrainingVersion", training_version)
  params.put("GitCommit", get_commit(default=""))
  params.put("GitBranch", get_short_branch(default=""))
  params.put("GitRemote", get_origin(default=""))
  params.put_bool("IsTestedBranch", is_tested_branch())
  params.put_bool("IsReleaseBranch", is_release_branch())

  # set dongle id
  reg_res = register(show_spinner=True)
  if reg_res:
    dongle_id = reg_res
  else:
    serial = params.get("HardwareSerial")
    raise Exception(f"Registration failed for device {serial}")
  os.environ['DONGLE_ID'] = dongle_id  # Needed for swaglog

  if not is_dirty():
    os.environ['CLEAN'] = '1'

  # init logging
  sentry.init(sentry.SentryProject.SELFDRIVE)
  cloudlog.bind_global(dongle_id=dongle_id,
                       version=get_version(),
                       origin=get_normalized_origin(),
                       branch=get_short_branch(),
                       commit=get_commit(),
                       dirty=is_dirty(),
                       device=HARDWARE.get_device_type())

  # opkr
  if os.path.isfile('/data/log/error.txt'):
    os.remove('/data/log/error.txt')

def manager_prepare() -> None:
  for p in managed_processes.values():
    p.prepare()


def manager_cleanup() -> None:
  # send signals to kill all procs
  for p in managed_processes.values():
    p.stop(block=False)

  # ensure all are killed
  for p in managed_processes.values():
    p.stop(block=True)

  cloudlog.info("everything is dead")


def manager_thread() -> None:
  cloudlog.bind(daemon="manager")
  cloudlog.info("manager start")
  cloudlog.info({"environ": os.environ})

  params = Params()

  ignore: List[str] = []
  if params.get("DongleId", encoding='utf8') in (None, UNREGISTERED_DONGLE_ID):
    ignore += ["manage_athenad", "uploader"]
  if os.getenv("NOBOARD") is not None:
    ignore.append("pandad")
  ignore += [x for x in os.getenv("BLOCK", "").split(",") if len(x) > 0]

  sm = messaging.SubMaster(['deviceState', 'carParams'], poll=['deviceState'])
  pm = messaging.PubMaster(['managerState'])

  write_onroad_params(False, params)
  ensure_running(managed_processes.values(), False, params=params, CP=sm['carParams'], not_run=ignore)

  started_prev = False

  while True:
    sm.update()

    started = sm['deviceState'].started

    if started and not started_prev:
      params.clear_all(ParamKeyType.CLEAR_ON_ONROAD_TRANSITION)
    elif not started and started_prev:
      params.clear_all(ParamKeyType.CLEAR_ON_OFFROAD_TRANSITION)

    # update onroad params, which drives boardd's safety setter thread
    if started != started_prev:
      write_onroad_params(started, params)

    started_prev = started

    ensure_running(managed_processes.values(), started, params=params, CP=sm['carParams'], not_run=ignore)

    running = ' '.join("%s%s\u001b[0m" % ("\u001b[32m" if p.proc.is_alive() else "\u001b[31m", p.name)
                       for p in managed_processes.values() if p.proc)
    print(running)
    cloudlog.debug(running)

    # send managerState
    msg = messaging.new_message('managerState')
    msg.managerState.processes = [p.get_process_state_msg() for p in managed_processes.values()]
    pm.send('managerState', msg)

    # Exit main loop when uninstall/shutdown/reboot is needed
    shutdown = False
    for param in ("DoUninstall", "DoShutdown", "DoReboot"):
      if params.get_bool(param):
        shutdown = True
        params.put("LastManagerExitReason", f"{param} {datetime.datetime.now()}")
        cloudlog.warning(f"Shutting down manager - {param} set")

    if shutdown:
      break


def main() -> None:
  prepare_only = os.getenv("PREPAREONLY") is not None

  manager_init()

  # Start UI early so prepare can happen in the background
  if not prepare_only:
    managed_processes['ui'].start()

  manager_prepare()

  if prepare_only:
    return

  # SystemExit on sigterm
  signal.signal(signal.SIGTERM, lambda signum, frame: sys.exit(1))

  try:
    manager_thread()
  except Exception:
    traceback.print_exc()
    sentry.capture_exception()
  finally:
    manager_cleanup()

  params = Params()
  if params.get_bool("DoUninstall"):
    cloudlog.warning("uninstalling")
    HARDWARE.uninstall()
  elif params.get_bool("DoReboot"):
    cloudlog.warning("reboot")
    HARDWARE.reboot()
  elif params.get_bool("DoShutdown"):
    cloudlog.warning("shutdown")
    HARDWARE.shutdown()


if __name__ == "__main__":
  unblock_stdout()

  try:
    main()
  except Exception:
    add_file_handler(cloudlog)
    cloudlog.exception("Manager failed to start")

    try:
      managed_processes['ui'].stop()
    except Exception:
      pass

    # Show last 3 lines of traceback
    error = traceback.format_exc(-3)
    error = "Manager failed to start\n\n" + error
    with TextWindow(error) as t:
      t.wait_for_exit()

    raise

  # manual exit because we are forked
  sys.exit(0)
