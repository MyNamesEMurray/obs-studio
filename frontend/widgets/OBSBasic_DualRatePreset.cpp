#include "OBSBasic.hpp"

#include <qt-wrappers.hpp>

#include <QMessageBox>

#include <filesystem>

static bool EncoderAvailable(const char *id)
{
	const char *type;
	for (size_t i = 0; obs_enum_encoder_types(i, &type); i++) {
		if (strcmp(type, id) == 0)
			return true;
	}
	return false;
}

static const char *FirstAvailableEncoder(std::initializer_list<const char *> ids)
{
	for (const char *id : ids) {
		if (EncoderAvailable(id))
			return id;
	}
	return nullptr;
}

static OBSData ReadEncoderJson(const std::filesystem::path &path)
{
	OBSDataAutoRelease data = obs_data_create_from_json_file(path.u8string().c_str());
	if (!data)
		data = obs_data_create();
	return OBSData(data);
}

static void WriteEncoderJson(const std::filesystem::path &path, obs_data_t *data)
{
	obs_data_save_json_safe(data, path.u8string().c_str(), "tmp", "bak");
}

void OBSBasic::on_actionApplyDualRatePreset_triggered()
{
	if (Active()) {
		QMessageBox::information(this, QTStr("Basic.DualRatePreset.Title"), QTStr("Basic.DualRatePreset.Active"));
		return;
	}

	const char *streamId = FirstAvailableEncoder({"obs_nvenc_h264_tex", "h264_texture_amf", "obs_qsv11_v2", "obs_x264"});
	const char *recordId = FirstAvailableEncoder({"obs_qsv11_av1", "obs_nvenc_av1_tex", "obs_nvenc_hevc_tex"});
	if (!streamId) {
		QMessageBox::warning(this, QTStr("Basic.DualRatePreset.Title"), QTStr("Basic.DualRatePreset.NoEncoder"));
		return;
	}

	struct obs_video_info ovi;
	bool rescale = recordId && obs_get_video_info(&ovi) && ovi.output_height > 1080;

	QString recordText = recordId ? QString::fromUtf8(obs_encoder_get_display_name(recordId))
				      : QTStr("Basic.DualRatePreset.SharedEncoder");
	QString extra = rescale ? "\n" + QTStr("Basic.DualRatePreset.Rescale") : QString();

	if (QMessageBox::question(this, QTStr("Basic.DualRatePreset.Title"),
				  QTStr("Basic.DualRatePreset.Confirm")
					  .arg(recordText, QString::fromUtf8(obs_encoder_get_display_name(streamId)), extra)) !=
	    QMessageBox::Yes)
		return;

	config_t *config = Config();
	config_set_string(config, "Output", "Mode", "Advanced");
	config_set_int(config, "Output", "StreamFpsDivisor", 2);
	config_set_string(config, "AdvOut", "Encoder", streamId);
	config_set_string(config, "AdvOut", "RecEncoder", recordId ? recordId : "none");
	config_set_string(config, "AdvOut", "RecType", "Standard");
	config_set_string(config, "AdvOut", "RescaleRes", rescale ? "1920x1080" : "");
	config_set_int(config, "AdvOut", "RescaleFilter", rescale ? OBS_SCALE_BICUBIC : OBS_SCALE_DISABLE);
	config_save_safe(config, "tmp", nullptr);

	const std::filesystem::path dir = GetCurrentProfile().path;

	OBSData stream = ReadEncoderJson(dir / std::filesystem::u8path("streamEncoder.json"));
	if (!obs_data_has_user_value(stream, "bitrate"))
		obs_data_set_int(stream, "bitrate", 6000);
	obs_data_set_string(stream, "rate_control", "CBR");
	obs_data_set_int(stream, "keyint_sec", 2);
	if (strstr(streamId, "nvenc")) {
		obs_data_set_string(stream, "preset2", "p3");
		obs_data_set_int(stream, "bf", 2);
	} else if (strcmp(streamId, "obs_x264") == 0) {
		obs_data_set_string(stream, "preset", "veryfast");
	}
	WriteEncoderJson(dir / std::filesystem::u8path("streamEncoder.json"), stream);

	if (recordId) {
		OBSData record = ReadEncoderJson(dir / std::filesystem::u8path("recordEncoder.json"));
		obs_data_set_string(record, "rate_control", "CQP");
		obs_data_set_int(record, "keyint_sec", 2);
		if (strcmp(recordId, "obs_qsv11_av1") == 0) {
			obs_data_set_int(record, "__ver", 2);
			obs_data_set_int(record, "cqp", 16);
			obs_data_set_string(record, "target_usage", "balanced");
		} else {
			obs_data_set_int(record, "cqp", 18);
			obs_data_set_string(record, "preset2", "p5");
		}
		WriteEncoderJson(dir / std::filesystem::u8path("recordEncoder.json"), record);
	}

	ResetOutputs();

	QMessageBox::information(this, QTStr("Basic.DualRatePreset.Title"), QTStr("Basic.DualRatePreset.Done"));
}
