local util = nil      ---@type Util

local AETools = AETools or {}     ---@class AETools
AETools.__index = AETools


function AETools:new(_util, ...)
    local o = {}
    setmetatable(o, self)
    util = _util
    self.key_frame_info = {}
    return o
end

function AETools:addKeyFrameInfo(in_val, out_val, frame, val)
    local key_frame_count = #self.key_frame_info
    if key_frame_count == 0 and frame > 0 then
        self.key_frame_info[key_frame_count + 1] = {
            ["v_in"] = in_val,
            ["v_out"] = out_val,
            ["cur_frame"] = 0,
            ["value"] = val
        }
    end

    key_frame_count = #self.key_frame_info
    self.key_frame_info[key_frame_count + 1] = {
        ["v_in"] = in_val,
        ["v_out"] = out_val,
        ["cur_frame"] = frame,
        ["value"] = val
    }

    self:_updateKeyFrameInfo()
end

function AETools:_updateKeyFrameInfo()
    if self.key_frame_info and #self.key_frame_info > 0 then
        self.finish_frame_time = self.key_frame_info[#self.key_frame_info]["cur_frame"]
    end
end

function AETools:getCurPartVal(_progress)

    local part_id, part_progress = self:_getCurPart(_progress)

    local frame1 = self.key_frame_info[part_id-1]
    local frame2 = self.key_frame_info[part_id]

    local info1 = frame1["v_out"]
    local info2 = frame2["v_in"]

    local duration = frame2['cur_frame'] - frame2['cur_frame']
    local diff = math.abs(frame1['value']-frame2['value'])

    local average = diff/(duration + 0.001) + 0.001
    local affect_val1 = info1[2]/100
    local affect_val2 = 1-info2[2]/100

    local bezier_val = {
        affect_val1,            
        info1[1]/average * affect_val1,     
        affect_val2,            
        1-info2[1]/average * affect_val2
    }

    local progress = util.bezier(bezier_val)(part_progress, 0, 1, 1)
    return util.mix(frame1["value"], frame2["value"], progress)

end

function AETools:_getCurPart(progress)
    if progress > 0.999 then
        return #self.key_frame_info, 1
    end

    for i = 1, #self.key_frame_info do
        local info = self.key_frame_info[i]
        if progress < info["cur_frame"]/self.finish_frame_time then
            return i, util.remap01(
                self.key_frame_info[i-1]["cur_frame"]/self.finish_frame_time,
                self.key_frame_info[i]["cur_frame"]/self.finish_frame_time,
                progress
            )
        end
    end
end

function AETools:clear()
    self.key_frame_info = {}
    self:_updateKeyFrameInfo()
end

function AETools:test()
    Amaz.LOGI("lrc "..tostring(#self.key_frame_info), "test123")
end

return AETools