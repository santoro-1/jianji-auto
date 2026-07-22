
local util = {}     ---@class Util
local json = cjson.new()
local rootDir = nil
local record_t = {}

local function getBezierValue(controls, t)
    local ret = {}
    local xc1 = controls[1]
    local yc1 = controls[2]
    local xc2 = controls[3]
    local yc2 = controls[4]
    ret[1] = 3*xc1*(1-t)*(1-t)*t+3*xc2*(1-t)*t*t+t*t*t
    ret[2] = 3*yc1*(1-t)*(1-t)*t+3*yc2*(1-t)*t*t+t*t*t
    return ret
end

local function getBezierDerivative(controls, t)
    local ret = {}
    local xc1 = controls[1]
    local yc1 = controls[2]
    local xc2 = controls[3]
    local yc2 = controls[4]
    ret[1] = 3*xc1*(1-t)*(1-3*t)+3*xc2*(2-3*t)*t+3*t*t
    ret[2] = 3*yc1*(1-t)*(1-3*t)+3*yc2*(2-3*t)*t+3*t*t
    return ret
end

local function getBezierTfromX(controls, x)
    local ts = 0
    local te = 1
    -- divide and conque
    repeat
        local tm = (ts+te)/2
        local value = getBezierValue(controls, tm)
        if(value[1]>x) then
            te = tm
        else
            ts = tm
        end
    until(te-ts < 0.0001)

    return (te+ts)/2
end

local function changeVec2ToTable(val)
    return {val.x, val.y}
end

local function changeVec3ToTable(val)
    return {val.x, val.y, val.z}
end

local function changeVec4ToTable(val)
    return {val.x, val.y, val.z, val.w}
end

local function changeCol3ToTable(val)
    return {val.r, val.g, val.b}
end

local function changeCol4ToTable(val)
    return {val.r, val.g, val.b, val.a}
end

local function changeTable2Vec4(t)
    return Amaz.Vector4f(t[1], t[2], t[3], t[4])
end

local function changeTable2Vec3(t)
    return Amaz.Vector3f(t[1], t[2], t[3])
end

local function changeTable2Vec2(t)
    return Amaz.Vector2f(t[1], t[2])
end

local function changeTable2Col3(t)
    return Amaz.Color(t[1], t[2], t[3])
end

local function changeTable2Col4(t)
    return Amaz.Color(t[1], t[2], t[3], t[4])
end

local _typeSwitch = {
    ["vec4"] = function(v)
        return changeVec4ToTable(v)
    end,
    ["vec3"] = function(v)
        return changeVec3ToTable(v)
    end,
    ["vec2"] = function(v)
        return changeVec2ToTable(v)
    end,
    ["float"] = function(v)
        return tonumber(v)
    end,
    ["string"] = function(v)
        return tostring(v)
    end,
    ["col3"] = function(v)
        return changeCol3ToTable(v)
    end,
    ["col4"] = function(v)
        return changeCol4ToTable(v)
    end,

    -- change table to userdata
    ["_vec4"] = function(v)
        return changeTable2Vec4(v)
    end,
    ["_vec3"] = function(v)
        return changeTable2Vec3(v)
    end,
    ["_vec2"] = function(v)
        return changeTable2Vec2(v)
    end,
    ["_float"] = function(v)
        return tonumber(v)
    end,
    ["_string"] = function(v)
        return tostring(v)
    end,
    ["_col3"] = function(v)
        return changeTable2Col3(v)
    end,
    ["_col4"] = function(v)
        return changeTable2Col4(v)
    end,
}

local function createTableContent()
    -- Amaz.LOGI("lrc", "createTableContent")
    local t = {}
    for k,v in pairs(record_t) do
        t[k] = {}
        t[k]["type"] = v["type"]
        t[k]["val"] = v["func"](v["val"])
    end
    return t
end

function util.registerParams(_name, _data, _type)
    record_t[_name] = {
        ["type"] = _type,
        ["val"] = _data,
        ["func"] = _typeSwitch[_type]
    }
end

function util.getRegistedParams()
    return record_t
end

function util.setRegistedVal(_name, _data)
    record_t[_name]["val"] = _data
end

function util.getRootDir()
    if rootDir == nil then
        local str = debug.getinfo(2, "S").source
        rootDir = str:match("@?(.*/)")
    end
    Amaz.LOGI("lrc getRootDir 123", tostring(rootDir))
    return rootDir
end

function util.registerRootDir(path)
    rootDir = path
end

function util.bezier(controls)
    local control = controls
    if type(control) ~= "table" then
        control = changeVec4ToTable(controls)
    end
    return function (t, b, c, d)
        t = t/d
        local tvalue = getBezierTfromX(control, t)
        local value =  getBezierValue(control, tvalue)
        return b + c * value[2]
    end
end

function util.remap01(a,b,x)
    if x < a then return 0 end
    if x > b then return 1 end
    return (x-a)/(b-a)
end

function util.mix(a, b, x)
    return a * (1-x) + b * x
end

function util.CreateJsonFile(file_path)
    local t = createTableContent()
    local content = json.encode(t)
    local file = io.open(util.getRootDir()..file_path, "w+b")
    if file then
      file:write(tostring(content))
      io.close(file)
    end
end

function util.ReadFromJson(file_path)
    local file = io.input(util.getRootDir()..file_path)
    local json_data = json.decode(io.read("*a"))
    local res = {}
    for k, v in pairs(json_data) do
        local func = _typeSwitch["_"..tostring(v["type"])]
        res[k] = func(v["val"])
    end
    return res
end

function util.bezierWithParams(input_val_4, min_val, max_val, in_val, reverse)
    if type(input_val_4) == "tabke" then
        if reverse == nil then
            return util.bezier(input_val_4)(util.remap01(min_val, max_val, in_val), 0, 1, 1)
        else
            return util.bezier(input_val_4)(1-util.remap01(min_val, max_val, in_val), 0, 1, 1)
        end
    else
        if reverse == nil then
            return util.bezier(util.changeVec4ToTable(input_val_4))(util.remap01(min_val, max_val, in_val), 0, 1, 1)
        else
            return util.bezier(util.changeVec4ToTable(input_val_4))(1-util.remap01(min_val, max_val, in_val), 0, 1, 1)
        end
    end
end

function util.test()
    Amaz.LOGI("lrc", "test123")
end

local AETools = AETools or {}     ---@class AETools
AETools.__index = AETools

function AETools:new(frameRate)
    local self = setmetatable({}, AETools)
    self.key_frame_info = {}
    self.frameRate = frameRate == nil and 16 or frameRate
    return self
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

function AETools._remap01(a,b,x)
    if x < a then return 0 end
    if x > b then return 1 end
    return (x-a)/(b-a)
end

function AETools._cubicBezier(p1, p2, p3, p4, t)
    return {
        p1[1]*(1.-t)*(1.-t)*(1.-t) + 3*p2[1]*(1.-t)*(1.-t)*t + 3*p3[1]*(1.-t)*t*t + p4[1]*t*t*t,
        p1[2]*(1.-t)*(1.-t)*(1.-t) + 3*p2[2]*(1.-t)*(1.-t)*t + 3*p3[2]*(1.-t)*t*t + p4[2]*t*t*t,
    }
end

function AETools:_cubicBezier01(_bezier_val, p)
    local x = self:_getBezier01X(_bezier_val, p)
    return self._cubicBezier(
        {0,0},
        {_bezier_val[1], _bezier_val[2]},
        {_bezier_val[3], _bezier_val[4]},
        {1,1},
        x
    )[2]
end

function AETools:_getBezier01X(_bezier_val, x)
    local ts = 0
    local te = 1
    -- divide and conque
    repeat
        local tm = (ts+te)*0.5
        local value = self._cubicBezier(
            {0,0},
            {_bezier_val[1], _bezier_val[2]},
            {_bezier_val[3], _bezier_val[4]},
            {1,1},
            tm)
        if(value[1]>x) then
            te = tm
        else
            ts = tm
        end
    until(te-ts < 0.0001)

    return (te+ts)*0.5
end

function AETools._mix(a, b, x)
    return a * (1-x) + b * x
end

function AETools:_updateKeyFrameInfo()
    if self.key_frame_info and #self.key_frame_info > 0 then
        self.finish_frame_time = self.key_frame_info[#self.key_frame_info]["cur_frame"]
    end
end

function AETools._getDiff(val1, val2)
    local res = nil
    if type(val1) == "table" then
        res = {}
        for i = 1, #val1 do
            res[i] = math.abs(val1-val2)
        end
    else
        res = math.abs(val1-val2)
    end
    return res
end

function AETools:_getSingleCurPartVal(val1, val2, duration, info1, info2, part_progress)
    local diff = math.abs(val1-val2)
    local average = diff/duration + 0.0001

    local x1 = info1[2]/100
    local y1 = x1*info1[1]/average
    local x2 = 1-info2[2]/100
    local y2 = 1-(1-x2)*info2[1]/average

    if val1 > val2 then
        x1 = info1[2]/100
        y1 = -x1*info1[1]/average
        x2 = info2[2]/100
        y2 = 1+x2*info2[1]/average
        x2 = 1-x2
        if(x1 < 0.0002)then y1 = 0 end
        if(y2 < 0.0002)then y2 = 0 end
    end
    local bezier_val = {x1, y1, x2, y2}
    local progress = self:_cubicBezier01(bezier_val, part_progress)

    local res = self._mix(val1, val2, progress)
    return res
end


function AETools:getCurPartVal(_progress, hard_cut)
    
    local part_id, part_progress = self:_getCurPart(_progress)

    local frame1 = self.key_frame_info[part_id-1]
    local frame2 = self.key_frame_info[part_id]

    if hard_cut == true then
        return frame1["value"]
    end

    local info1 = frame1["v_out"]
    local info2 = frame2["v_in"]

    info1[2] = info1[2] < 0.011 and 0 or info1[2]
    info2[2] = info2[2] < 0.011 and 0 or info2[2]

    local duration = (frame2["cur_frame"]-frame1["cur_frame"])/self.frameRate

    local res = nil
    if type(frame1["value"]) == "table" then
        res = {}
        for i = 1, #frame1["value"] do
            res[i] = self:_getSingleCurPartVal(frame1["value"][i], frame2["value"][i], duration, info1, info2, part_progress)
        end
    else
        res = self:_getSingleCurPartVal(frame1["value"], frame2["value"], duration, info1, info2, part_progress)
    end

    return res

end

function AETools:_getCurPart(progress)
    if progress > 0.999 then
        return #self.key_frame_info, 1
    end

    for i = 1, #self.key_frame_info do
        local info = self.key_frame_info[i]
        if progress < info["cur_frame"]/self.finish_frame_time then
            return i, self._remap01(
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



-- local ae_attribute = {
-- 	["ADBE_Rotate_X_0_0"]={
-- 		[1]={{0, 33.333333, }, {0, 58.8673901584204, }, 0, 0, }, 
-- 		[2]={{214.570556864316, 30.8410633530931, }, {150.553587950243, 17.447991734746, }, 21, 329.542106330619, }, 
-- 		[3]={{0, 2.87975382581442, }, {0, 16.666666667, }, 33, 360, }, 
-- 	}, 
-- }

local function clamp(min, max, value)
	return math.min(math.max(value, 0), 1)
end

local function saturate(value)
	return clamp(0, 1, value)
end

local function lerp(a, b, c)
	c = saturate(0, 1, c)
	return (1 - c) * a + c * b
end

local function lerpVector3(a, b, c)
	c = saturate(0, 1, c)
	return Amaz.Vector3f(
		lerp(a.x, b.x, c),
		lerp(a.y, b.y, c),
		lerp(a.z, b.z, c)
	)
end

local function remap(smin, smax, dmin, dmax, value)
	return (value - smin) / (smax - smin) * (dmax - dmin) + dmin
end

local exports = exports or {}
local Transform = Transform or {}
Transform.__index = Transform
function Transform.new(construct, ...)
    local self = setmetatable({}, Transform)
    self.duration = 1.0
    self.count = 0
    if construct and Transform.constructor then Transform.constructor(self, ...) end
    return self
end

function Transform:constructor()

end
local function myArray(num)
    local startArray={}
    local resultArray={}
    for i=1,num do
        startArray[i]=i
    end
    for i=1,num do
        local tempnum=math.random(1,num-i+1)
        resultArray[i]=startArray[tempnum]
        startArray[tempnum]=startArray[num-i+1]
    end
    return resultArray
end

function Transform:initKeyFrame(attribute_table, frameRate) 
    for _name, info_list in pairs(attribute_table) do
        local tool = AETools:new(frameRate)
        for i = 1, #info_list do
            tool:addKeyFrameInfo(info_list[i][1], info_list[i][2], info_list[i][3], info_list[i][4])
        end
		Amaz.LOGI("====>wdg8",_name)
        self[_name] = tool
    end
end

function Transform:isvalidchar(char)
    local code = char.utf8code
    if code == ' ' or code == '\r' or code == '\n' then
        return false
    end
    return true
end

function Transform:onUpdate()
	self.textNum = self.text.chars:size()
	self.numArray={}

    for i = 1,self.textNum do
        local char = self.text.chars:get(i - 1)
		if self:isvalidchar(char) then
			table.insert(self.numArray,i)
		end
	end
end

function Transform:onStart(comp) 
	self.text = comp.entity:getComponent('SDFText')
    if self.text == nil then
        local text = comp.entity:getComponent('Text')
        if text ~= nil then
			self.text = comp.entity:addComponent('SDFText')
            self.text:setTextWrapper(text)
        end
    end
	self.textNum = self.text.chars:size()
	self.numArray={}

	local count = 0
	local ae_attribute = {}
    for i = 1,self.textNum do
        local char = self.text.chars:get(i - 1)
		if self:isvalidchar(char) then
			table.insert(self.numArray,i)
		end
	end

	local validcharCount = #self.numArray
	for i = 1, validcharCount do
		local key = "AE_SCALE"..i
		ae_attribute[key] = {}
		if validcharCount == i then
			ae_attribute[key] =
			{
				[1]={{0, 16.666666667, }, {600, 16.666666667, }, 14.0000142415365, {0, 0, 100, }, }, 
				[2]={{600, 16.666666667, }, {0, 16.666666667, }, 19.0000193277995, {100, 100, 100, }, }, 
			}
		elseif i == 1 then
			ae_attribute[key]={
				[1]={{0, 16.666666667, }, {600, 16.666666667, }, 0, {0, 0, 100, }, }, 
				[2]={{600, 16.666666667, }, {0, 16.666666667, }, 5.00000508626302, {100, 100, 100, }, }, 
				[3]={{600, 16.666666667, }, {0, 16.666666667, }, 19.0000193277995, {100, 100, 100, }, }, 
			}
		else
			local value0 = (i-1)*(19-5)/(validcharCount-1)
			local value1 = 5 + (i-1)*(19-5)/(validcharCount-1)
			ae_attribute[key]={
				[1]={{0, 16.666666667, }, {600, 16.666666667, }, value0, {0, 0, 100, }, }, 
				[2]={{600, 16.666666667, }, {0, 16.666666667, }, value1, {100, 100, 100, }, }, 
				[3]={{600, 16.666666667, }, {0, 16.666666667, }, 19.0000193277995, {100, 100, 100, }, }, 
			}

		end

	end
	Amaz.LOGI("=====wdg2=",#ae_attribute["AE_SCALE1"])
	self:initKeyFrame(ae_attribute, 16)
    self.org_gap = self.text.wordGap;
end

local function getBezierValue(controls, t)
    local ret = {}
    local xc1 = controls[1]
    local yc1 = controls[2]
    local xc2 = controls[3]
    local yc2 = controls[4]
    ret[1] = 3*xc1*(1-t)*(1-t)*t+3*xc2*(1-t)*t*t+t*t*t
    ret[2] = 3*yc1*(1-t)*(1-t)*t+3*yc2*(1-t)*t*t+t*t*t
    return ret
end

local function getBezierTfromX(controls, x)
    local ts = 0
    local te = 1
    -- divide and conque
    repeat
        local tm = (ts+te)/2
        local value = getBezierValue(controls, tm)
        if(value[1]>x) then
            te = tm
        else
            ts = tm
        end
    until(te-ts < 0.0001)

    return (te+ts)/2
end

local function bezier(controls)
	return function (t, b, c, d)
		t = t/d
		local tvalue = getBezierTfromX(controls, t)
		local value =  getBezierValue(controls, tvalue)
		return b + c * value[2]
	end
end

function clamp(min, max, value)
	return math.min(math.max(value, 0), 1)
end

function saturate(value)
	return clamp(0, 1, value)
end

function lerp(a, b, c)
	c = saturate(0, 1, c)
	return (1 - c) * a + c * b
end

function lerpVector3(a, b, c)
	c = saturate(0, 1, c)
	return Amaz.Vector3f(
		lerp(a.x, b.x, c),
		lerp(a.y, b.y, c),
		lerp(a.z, b.z, c)
	)
end

function remap(smin, smax, dmin, dmax, value)
	return (value - smin) / (smax - smin) * (dmax - dmin) + dmin
end

function remapClamped(smin, smax, dmin, dmax, value)
	return saturate(value - smin) / (smax - smin) * (dmax - dmin) + dmin
end

function remapVector3(smin, smax, dmin, dmax, value)
	return Amaz.Vector3f(
		remap(smin.x, smax.x, dmin.x, dmax.x, value.x),
		remap(smin.y, smax.y, dmin.y, dmax.y, value.y),
		remap(smin.z, smax.z, dmin.z, dmax.z, value.z)
	) 
end

function remapVector4(smin, smax, dmin, dmax, value)
	return Amaz.Vector3f(
		remap(smin.x, smax.x, dmin.x, dmax.x, value.x),
		remap(smin.y, smax.y, dmin.y, dmax.y, value.y),
		remap(smin.z, smax.z, dmin.z, dmax.z, value.z),
		remap(smin.w, smax.w, dmin.w, dmax.w, value.w)
	) 
end



function Transform:seek(time)
	self.count = self.text.chars:size()
	self.progress = time % (self.duration+0.00001) / (self.duration+0.000001)
    
	self.numArray={}
    for i = 1,self.count do
        local char = self.text.chars:get(i - 1)
		if self:isvalidchar(char) then
			table.insert(self.numArray,i)
		end
	end

	local validcharCount = #self.numArray
	local line_duration= 0.25
	local line_sub_duration = 0.25

	if validcharCount >= 1 then
		for i = 1, validcharCount do
			local index = self.numArray[i] -1
			local char = self.text.chars:get(index)
			local str_index = index + 1
			local key = "AE_SCALE"..str_index
            local start_p = 0 
            if validcharCount > 1 then 
			    start_p = (i-1)*(1.-line_sub_duration)*line_duration/(validcharCount-1)
            end
			local end_p = start_p + line_sub_duration*line_duration
			local scale = 0
			if self.progress >= start_p and self.progress <= end_p then
				scale = 1*(self.progress-start_p)/(end_p-start_p)
			elseif self.progress > end_p then
				local del = 1.0 - end_p
				local pt = (self.progress - end_p)/del
				scale = 1+0.4*math.sin(pt*7*3.1415926)/math.exp(pt*3)
			end
			-- local scalet = self[key]:getCurPartVal(self.progress)
			-- local scale = scalet[1]/100
			-- Amaz.LOGI("ekdkkdkdkkdkd222===",str_index)
			char.scale = Amaz.Vector3f(scale, scale, scale)
		end
	end

    -- if self.text.wordGap < 0.12 then
    --     self.text.wordGap =  0.12
    -- end
    -- if self.text.lineGap <  0.12 then
    --     self.text.lineGap =  0.12
    -- end

    -- if self.progress > 0.8 then
    --     self.text.lineGap = 0.12 - 0.12*(self.progress - 0.8)/0.2
    --     self.text.wordGap =  0.12 - 0.12*(self.progress - 0.8)/0.2
    -- end
	-- for i = 1, self.count do
	-- 	local char = self.text.chars:get(self.numArray[i]-1)
	-- 	local scale = self.ADBE_Rotate_X_0_0:getCurPartVal(self.progress)
	-- 	char.scale = scale
	-- end

    local chars = self.text.chars 
    self.text.chars= chars
end

function Transform:setDuration(duration)
   self.duration = duration
end



function Transform:resetData()
    for i = 1, self.text.chars:size() do
        local char = self.text.chars:get(i - 1)
        if char.rowth ~= -1 then
            char.position = char.initialPosition
            char.rotate = Amaz.Vector3f(0, 0, 0)
            char.scale = Amaz.Vector3f(1, 1, 1)
            char.color = Amaz.Vector4f(1, 1, 1, 1)
        end
    end
    if self.text ~= nil then
    	local chars = self.text.chars 
   		self.text.chars= chars
   	end
    -- self.text.wordGap = self.org_gap
end

function Transform:clear()
    self:resetData()
end

function Transform:onLeave()
    self:resetData()
end

exports.Transform = Transform
return exports
