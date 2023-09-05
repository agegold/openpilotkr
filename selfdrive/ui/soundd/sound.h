#pragma once

#include <tuple>

#include <QMap>
#include <QSoundEffect>
#include <QString>

#include "system/hardware/hw.h"
#include "selfdrive/ui/ui.h"

const std::tuple<AudibleAlert, QString, int> sound_list[] = {
  // AudibleAlert, file name, loop count
  {AudibleAlert::ENGAGE, "engage.wav", 0},
  {AudibleAlert::DISENGAGE, "disengage.wav", 0},
  {AudibleAlert::REFUSE, "refuse.wav", 0},

  {AudibleAlert::PROMPT, "prompt.wav", 0},
  {AudibleAlert::PROMPT_REPEAT, "prompt.wav", QSoundEffect::Infinite},
  {AudibleAlert::PROMPT_DISTRACTED, "prompt_distracted.wav", QSoundEffect::Infinite},

  {AudibleAlert::WARNING_SOFT, "warning_soft.wav", QSoundEffect::Infinite},
  {AudibleAlert::WARNING_IMMEDIATE, "warning_immediate.wav", 8},
  {AudibleAlert::WARNING, "warning.wav", 0},
  {AudibleAlert::DINGDONG, "dingdong.wav", 0},
};

class Sound : public QObject {
public:
  explicit Sound(QObject *parent = 0);

protected:
  void update();
  void setAlert(const Alert &alert);

  SubMaster sm;
  Alert current_alert = {};
  QMap<AudibleAlert, QPair<QSoundEffect *, int>> sounds;
  int current_volume = -1;
};
