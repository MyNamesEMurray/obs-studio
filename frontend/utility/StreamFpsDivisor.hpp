#pragma once

#include <algorithm>
#include <cstring>
#include <sstream>
#include <string>

#include <obs.hpp>
#include <util/config-file.h>

static inline uint32_t GetStreamFpsDivisor(config_t *config)
{
	if (config_has_user_value(config, "Output", "StreamFpsDivisor"))
		return (uint32_t)std::clamp((int)config_get_int(config, "Output", "StreamFpsDivisor"), 1, 4);
	return config_get_bool(config, "Output", "StreamHalfRate") ? 2 : 1;
}

/* With a shared encoder the output drops non-reference B-frames, so the encoder must produce
 * divisor - 1 of them between each kept frame. */
static inline void ApplyDivisorEncoderSettings(obs_encoder_t *enc, uint32_t divisor)
{
	if (divisor < 2 || obs_encoder_active(enc))
		return;

	const char *id = obs_encoder_get_id(enc);
	int bf = (int)divisor - 1;
	OBSDataAutoRelease cur = obs_encoder_get_settings(enc);
	OBSDataAutoRelease upd = obs_data_create();

	if (strcmp(id, "obs_x264") == 0) {
		std::istringstream in(obs_data_get_string(cur, "x264opts"));
		std::string opts, tok;
		while (in >> tok) {
			if (tok.rfind("bframes=", 0) == 0 || tok.rfind("bf=", 0) == 0 || tok.rfind("b-adapt=", 0) == 0 ||
			    tok.rfind("b-pyramid=", 0) == 0)
				continue;
			opts += tok + " ";
		}
		opts += "b-adapt=0 b-pyramid=none";
		obs_data_set_string(upd, "x264opts", opts.c_str());
		obs_data_set_int(upd, "bf", bf);
	} else if (strstr(id, "nvenc")) {
		obs_data_set_int(upd, "bf", bf);
		obs_data_set_int(upd, "bframe_ref_mode", 0);
	} else {
		blog(LOG_INFO, "No automatic B-frame setup for encoder '%s'; set %d non-reference B-frame(s) manually",
		     id, bf);
		return;
	}

	obs_encoder_update(enc, upd);
	blog(LOG_INFO, "Set %d non-reference B-frame(s) on '%s' for stream frame rate divisor %u", bf, id, divisor);
}

/* dropDivisor is the divisor applied by the output (shared encoder); a separate stream encoder applies it itself. */
static inline void LogStreamEncoder(obs_encoder_t *enc, uint32_t dropDivisor)
{
	struct obs_video_info ovi;
	if (!obs_get_video_info(&ovi))
		return;
	uint32_t encDiv = obs_encoder_get_frame_rate_divisor(enc);
	if (!encDiv)
		encDiv = 1;
	double fps = (double)ovi.fps_num / ovi.fps_den / encDiv / dropDivisor;
	blog(LOG_INFO, "Stream encoder: %ux%u @ %.2f fps (encoder divisor %u, output frame drop divisor %u)",
	     obs_encoder_get_width(enc), obs_encoder_get_height(enc), fps, encDiv, dropDivisor);
	if (fps > 60.0 && encDiv * dropDivisor == 1)
		blog(LOG_INFO, "Stream runs above 60 fps; some services cap at 60. See 'Stream frame rate' in Advanced settings.");
}
