local exports = exports or {}
local TextAnim = TextAnim or {}
---@class TextAnim:ScriptComponent
---@field effectMaterial Material
---@field quad Mesh
---@field duration number
---@field progress number [UI(Range={0.0, 1.0}, Slider)]
---@field autoPlay boolean
---@field sharedMaterial Material
---@field rt ScreenRenderTexture
TextAnim.__index = TextAnim


local util = nil      ---@type Util

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
            {1,-1},
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
        local tmp_sum = 0
        for i = 1, #val1 do
            local tmp_v = math.abs(val1[i]-val2[i])
            tmp_sum = tmp_sum + tmp_v * tmp_v
        end
        res = math.sqrt(tmp_sum)
    else
        res = math.abs(val1-val2)
    end
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

    local duration = (frame2["cur_frame"]-frame1["cur_frame"])/self.frameRate
    local diff = self._getDiff(frame1["value"], frame2["value"])

    local average = diff/duration + 0.0001

    local x1 = info1[2]/100
    local y1 = x1*info1[1]/average
    local x2 = 1-info2[2]/100
    local y2 = 1-(1-x2)*info2[1]/average

    if type(frame1["value"]) == "number" then
        if frame1["value"] > frame2["value"] then
            x1 = info1[2]/100
            y1 = -x1*info1[1]/average
            x2 = info2[2]/100
            y2 = 1+x2*info2[1]/average
            x2 = 1-x2
        end

        local bezier_val = {x1, y1, x2, y2}

        local progress = self:_cubicBezier01(bezier_val, part_progress)

        return self._mix(frame1["value"], frame2["value"], progress)
    end

    local res = {}
    for i = 1, #frame1["value"] do

        if frame1["value"][i] > frame2["value"][i] then
            x1 = info1[2]/100
            y1 = -x1*info1[1]/average
            x2 = info2[2]/100
            y2 = 1+x2*info2[1]/average
            x2 = 1-x2
        end

        local bezier_val = {x1, y1, x2, y2}

        local progress = self:_cubicBezier01(bezier_val, part_progress)
        res[i] = self._mix(frame1["value"][i], frame2["value"][i], progress)
    end
    return res

end

function AETools:_getCurPart(progress)
    if progress > 0.999 then
        return #self.key_frame_info, 1.0
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

function AETools:test()
    Amaz.LOGI("lrc "..tostring(self.key_frame_info), tostring(#self.key_frame_info))
end


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

local function typeSwitch()
    return _typeSwitch
end

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
function util.remapNew(a,b,x)
    return (b - a) * x + a
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


function util.clamp(min, max, value)
	return math.min(math.max(value, min), max)
end

function util.test()
    Amaz.LOGI("lrc", "test123")
end

local ae_attribute = {
    
	["Position_X"]={
		[1]={{0, 16.666666667, }, {0, 16.666666667, }, 0, 442.022523231264, }, 
		[2]={{0, 16.666666667, }, {0, 16.666666667, }, 1, 442.022523231264, }, 
		[3]={{0, 16.666666667, }, {-281.948754116759, 30, }, 2, 442.022523231264, }, 
		[4]={{-1484.42949698917, 30, }, {-1484.42949698917, 30, }, 3, 425.105597984597, }, 
		[5]={{-3687.08204752013, 30, }, {-3687.08204752013, 30, }, 4, 352.956753413695, }, 
		[6]={{-5882.61238460122, 30, }, {-5882.61238460122, 30, }, 5, 203.880675137814, }, 
		[7]={{-3644.47407666004, 30, }, {-3644.47407666004, 30, }, 6, 0.00001034468119, }, 
		[8]={{-308.560017206932, 30, }, {-308.560017206932, 30, }, 7, -14.7877694574153, }, 
		[9]={{75.8582851076712, 30, }, {75.8582851076712, 30, }, 8, -18.5135906873645, }, 
		[10]={{365.014480173483, 30, }, {365.014480173483, 30, }, 9, -10.236272351046, }, 
		[11]={{390.591721325303, 30, }, {390.591721325303, 30, }, 10, 3.38727812260654, }, 
		[12]={{169.551430800751, 30, }, {169.551430800751, 30, }, 11, 13.1992309280034, }, 
		[13]={{-129.565079478582, 30, }, {-129.565079478582, 30, }, 12, 13.5603639704481, }, 
		[14]={{-310.596241114212, 30, }, {-310.596241114212, 30, }, 13, 5.42532615944396, }, 
		[15]={{-275.459905852021, 30, }, {-275.459905852021, 30, }, 14, -5.07541049603189, }, 
		[16]={{-73.0372330415833, 30, }, {-73.0372330415833, 30, }, 15, -11.1022681913467, }, 
		[17]={{149.635998062889, 30, }, {149.635998062889, 30, }, 16, -9.45764447843924, }, 
		[18]={{251.257431286416, 30, }, {251.257431286416, 30, }, 17, -2.12410830775294, }, 
		[19]={{183.604989510126, 30, }, {183.604989510126, 30, }, 18, 5.6178013984442, }, 
		[20]={{9.9709645348321, 30, }, {9.9709645348321, 30, }, 19, 8.89219106263429, }, 
		[21]={{-148.203011968849, 30, }, {-148.203011968849, 30, }, 20, 6.21605927052217, }, 
		[22]={{-194.269484930595, 30, }, {-194.269484930595, 30, }, 21, 0.0000103446812, }, 
		[23]={{-113.512886697937, 30, }, {-113.512886697937, 30, }, 22, -5.44010982508039, }, 
		[24]={{27.906703533634, 30, }, {27.906703533634, 30, }, 23, -6.8107628570588, }, 
		[25]={{134.281322985706, 30, }, {134.281322985706, 30, }, 24, -3.76570761309584, }, 
		[26]={{143.690664167344, 30, }, {143.690664167344, 30, }, 25, 1.24611652192239, }, 
		[27]={{62.3744856127989, 30, }, {62.3744856127989, 30, }, 26, 4.85573223677237, }, 
		[28]={{-47.6643290339145, 30, }, {-47.6643290339145, 30, }, 27, 4.98858565861548, }, 
		[29]={{-114.261971611047, 30, }, {-114.261971611047, 30, }, 28, 1.9958724947947, }, 
		[30]={{-101.336036229979, 30, }, {-101.336036229979, 30, }, 29, -1.86713263791022, }, 
		[31]={{-26.868896476046, 30, }, {-26.868896476046, 30, }, 30, -4.08428967888246, }, 
		[32]={{55.0480073465069, 30, }, {55.0480073465069, 30, }, 31, -3.47926642644074, }, 
		[33]={{92.4324434118187, 30, }, {92.4324434118187, 30, }, 32, -0.78140923815811, }, 
		[34]={{67.5445009372735, 30, }, {67.5445009372735, 30, }, 33, 2.06668017815746, }, 
		[35]={{3.66811286101406, 30, }, {3.66811286101406, 30, }, 34, 3.27126081799725, }, 
		[36]={{-54.5208412230247, 30, }, {-54.5208412230247, 30, }, 35, 2.2867669498139, }, 
		[37]={{-71.467749552931, 30, }, {-71.467749552931, 30, }, 36, 0.00001034468119, }, 
		[38]={{-41.7590573241943, 30, }, {-41.7590573241943, 30, }, 37, -2.0012980232762, }, 
		[39]={{10.2663025008905, 30, }, {10.2663025008905, 30, }, 38, -2.50553309472036, }, 
		[40]={{49.3993380597432, 30, }, {49.3993380597432, 30, }, 39, -1.38531987323509, }, 
		[41]={{52.8608412354358, 30, }, {52.8608412354358, 30, }, 40, 0.45842718880496, }, 
		[42]={{22.9462909105927, 30, }, {22.9462909105927, 30, }, 41, 1.78633060082763, }, 
		[43]={{0.81456737643888, 30, }, {0, 0, }, 42, 1.83520464341299, }, 
		[44]={{0.81456737643888, 30, }, {0, 0, }, 45, 1.83520464341299, }, 
	}, 
	["Position_Y"]={
		[1]={{0, 16.666666667, }, {0, 16.666666667, }, 0, 311.744525937817, }, 
		[2]={{0, 16.666666667, }, {0, 16.666666667, }, 1, 311.744525937817, }, 
		[3]={{0, 16.666666667, }, {-509.348180555382, 30, }, 2, 311.744525937817, }, 
		[4]={{-1922.40788800802, 30, }, {-1922.40788800802, 30, }, 3, 281.183635105106, }, 
		[5]={{-3438.35212398774, 30, }, {-3438.35212398774, 30, }, 4, 196.400052659643, }, 
		[6]={{-3273.33446161264, 30, }, {-3273.33446161264, 30, }, 5, 74.8825076699672, }, 
		[7]={{-1257.03955053116, 30, }, {-1257.03955053116, 30, }, 6, -0.00001503318794, }, 
		[8]={{-11.2644513565308, 30, }, {-11.2644513565308, 30, }, 7, -0.53986536039378, }, 
		[9]={{2.76932173623825, 30, }, {2.76932173623825, 30, }, 8, -0.67588211456626, }, 
		[10]={{13.3254071397919, 30, }, {13.3254071397919, 30, }, 9, -0.37370605622281, }, 
		[11]={{14.259143115687, 30, }, {14.259143115687, 30, }, 10, 0.12364231380526, }, 
		[12]={{6.18973210454678, 30, }, {6.18973210454678, 30, }, 11, 0.4818425307013, }, 
		[13]={{-4.72996971060172, 30, }, {-4.72996971060172, 30, }, 12, 0.49502624007064, }, 
		[14]={{-11.3387867981806, 30, }, {-11.3387867981806, 30, }, 13, 0.19804434807087, }, 
		[15]={{-10.0560815955092, 30, }, {-10.0560815955092, 30, }, 14, -0.18530096780659, }, 
		[16]={{-2.66633495246653, 30, }, {-2.66633495246653, 30, }, 15, -0.40532054764761, }, 
		[17]={{5.46268903088291, 30, }, {5.46268903088291, 30, }, 16, -0.34528106495138, }, 
		[18]={{9.17253355866458, 30, }, {9.17253355866458, 30, }, 17, -0.07755920580119, }, 
		[19]={{6.70277857732338, 30, }, {6.70277857732338, 30, }, 18, 0.20507094855748, }, 
		[20]={{0.36400518121888, 30, }, {0.36400518121888, 30, }, 19, 0.32460750883017, }, 
		[21]={{-5.4103757004099, 30, }, {-5.4103757004099, 30, }, 20, 0.22691125943018, }, 
		[22]={{-7.09210215525555, 30, }, {-7.09210215525555, 30, }, 21, -0.00001503318793, }, 
		[23]={{-4.14396007014345, 30, }, {-4.14396007014345, 30, }, 22, -0.19861486987664, }, 
		[24]={{1.01877653275126, 30, }, {1.01877653275126, 30, }, 23, -0.24865263739157, }, 
		[25]={{4.9021433319686, 30, }, {4.9021433319686, 30, }, 24, -0.13748827791279, }, 
		[26]={{5.24564560098256, 30, }, {5.24564560098256, 30, }, 25, 0.04547596252066, }, 
		[27]={{2.27707518762161, 30, }, {2.27707518762161, 30, }, 26, 0.17725045813987, }, 
		[28]={{-1.74005861389401, 30, }, {-1.74005861389401, 30, }, 27, 0.18210047377523, }, 
		[29]={{-4.17130655087682, 30, }, {-4.17130655087682, 30, }, 28, 0.07284694130832, }, 
		[30]={{-3.69942567773035, 30, }, {-3.69942567773035, 30, }, 29, -0.06817791927237, }, 
		[31]={{-0.98088981228927, 30, }, {-0.98088981228927, 30, }, 30, -0.14911859935107, }, 
		[32]={{2.00961098797458, 30, }, {2.00961098797458, 30, }, 31, -0.12703130800855, }, 
		[33]={{3.37438651968783, 30, }, {3.37438651968783, 30, }, 32, -0.028541940075, }, 
		[34]={{2.46581443732163, 30, }, {2.46581443732163, 30, }, 33, 0.07543188316867, }, 
		[35]={{0.1339100226503, 30, }, {0.1339100226503, 30, }, 34, 0.11940692616134, }, 
		[36]={{-1.99036598919435, 30, }, {-1.99036598919435, 30, }, 35, 0.08346648452752, }, 
		[37]={{-2.60903857760619, 30, }, {-2.60903857760619, 30, }, 36, -0.00001503318794, }, 
		[38]={{-1.52447771484114, 30, }, {-1.52447771484114, 30, }, 37, -0.07307583012572, }, 
		[39]={{0.37478694154712, 30, }, {0.37478694154712, 30, }, 38, -0.09148369607657, }, 
		[40]={{1.80339774950692, 30, }, {1.80339774950692, 30, }, 39, -0.05058861363334, }, 
		[41]={{1.9297651722729, 30, }, {1.9297651722729, 30, }, 40, 0.01672016889168, }, 
		[42]={{0.8376891475276, 30, }, {0.8376891475276, 30, }, 41, 0.06519729670072, }, 
		[43]={{0.02973701736074, 30, }, {0, 0, }, 42, 0.06698151774233, }, 
		[44]={{0.02973701736074, 30, }, {0, 0, }, 45, 0.06698151774233, }, 
	}, 
	["Scale"]={
		[1]={{0, 16.666666667, }, {205, 23.6197523971359, }, 2, 24, }, 
		[2]={{173.131641043253, 60.1246788896895, }, {0, 16.666666667, }, 6, 92.8177433067395, }, 
		[3]={{173.131641043253, 60.1246788896895, }, {0, 16.666666667, }, 45, 92.8177433067395, }, 
	}, 
	["Rotate"]={
		[1]={{0, 16.666666667, }, {-200, 23.6197523971359, }, 2, 32.9929203987122, }, 
		[2]={{-168.908918090978, 60.1246788896895, }, {0, 16.666666667, }, 6, 21.0000000994541, }, 
		[3]={{-168.908918090978, 60.1246788896895, }, {0, 16.666666667, }, 45, 21.0000000994541, }, 
	}, 
	["Alpha"]={
		[1]={{0, 16.666666667, }, {-300, 16.666666667, }, 35, 100, }, 
		[2]={{-300, 16.666666667, }, {0, 16.666666667, }, 45, 0, }, 
	}, 
    
	["Anchor_X"]={
		[1]={{0, 0, }, {-6200.00000004, 0.69767441860465, }, 2, 264.599975585938, }, 
		[2]={{-4400.00000004, 0.69767441860465, }, {0, 0, }, 45, 74.5999755859375, }, 
	}, 
	["Anchor_Y"]={
		[1]={{0, 0, }, {1333.333333352, 0.69767441860465, }, 2, 107.983825683594, }, 
		[2]={{9133.333333352, 0.69767441860465, }, {0, 0, }, 45, 285.983825683594, }, 
	}, 
	["AnchorScale"]={
		[1]={{0, 16.666666667, }, {10.4651162790697, 16.666666667, }, 2, 100, }, 
		[2]={{10.4651162790697, 16.666666667, }, {0, 16.666666667, }, 45, 115, }, 
	}, 
    
	["AnchorRotate"]={
		[1]={{0, 16.666666667, }, {-36.2790697674419, 16.666666667, }, 2, 7.00707960128784, }, 
		[2]={{-36.2790697674419, 16.666666667, }, {0, 16.666666667, }, 45, -44.9929203987122, }, 
	}, 
}


function TextAnim.new(construct, ...)
    local self = setmetatable({}, TextAnim)
    self.effectMaterial = nil
    self.curTime = 0
    self.progress = 0
    self.autoPlay = false
    self.duration = 1.0
    self.quad = nil
    self.offset = 222.9933470984
	self.cloneEntity = {}
	self.cloneEntityRenderer = {}
	self.ctrans = {}
    self.cloneEffectLayers = {}
	self.cloneEffectParams = {}
    if construct and TextAnim.constructor then TextAnim.constructor(self, ...) end
    return self
end

function TextAnim:constructor()
    self.name = "scriptComp"
end

function TextAnim:initKeyFrame() 
    for _name, info_list in pairs(ae_attribute) do
        local tool = AETools:new(45)
        for i = 1, #info_list do
            tool:addKeyFrameInfo(info_list[i][1], info_list[i][2], info_list[i][3], info_list[i][4])
        end
        self[_name] = tool
    end
end

local function getRootDir()
    local rootDir = nil
    if rootDir == nil then
        local str = debug.getinfo(2, "S").source
        rootDir = str:match("@?(.*/)")
    end
    -- Amaz.LOGI("lrc getRootDir 3", tostring(rootDir))
    return rootDir
end
function TextAnim:onStart(comp)
    self.text = comp.entity:getComponent('SDFText')
    self.camera = comp.entity.scene:findEntityBy("InfoSticker_camera_entity"):getComponent("Transform")
    if self.text == nil then
        local text = comp.entity:getComponent('Text')
        if text ~= nil then
            self.text = comp.entity:addComponent('SDFText')
            self.text:setTextWrapper(text)
        end
    end
    self.text1 = self.text.entity:getComponent('Text')
    self.textEntity = comp.entity
    self.renderer = nil
	if self.text ~= nil then
		self.renderer = comp.entity:getComponent("MeshRenderer")
	else
		self.renderer = comp.entity:getComponent("Sprite2DRenderer")
	end
    self.sortNumber = self.renderer.sortingOrder
    self.first = true
    local rect = self.text.rect

    self.trans = comp.entity:getComponent("Transform")

    self.parentTrans = self.trans.parent
    self.parentEntity = self.parentTrans.entity
    self.layer = tostring(self.parentEntity.name)
    -- comp.entity.layer = 1
    self.rootDir = getRootDir()
    self.rootDir = string.sub(self.rootDir,1,string.len(self.rootDir)-4) 
    self.cloneEntity = {}
    self.ctrans = {}
    self.material = {}
    -- self.effectText_prefab = Amaz.PrefabManager.loadPrefab(self.rootDir, self.rootDir .. "prefabs/pack.prefab")
    -- self.customEntity = self.effectText_prefab:instantiateToEntity(comp.entity.scene, self.rootEntity)
    -- self.blurEntity = comp.entity.scene:findEntityBy("Untitled"):getComponent("MeshRenderer").material
end

function TextAnim:setMatToSDFText(text, rendermaterial)

    text.renderToRT = true
    local materials = Amaz.Vector()
    local InsMaterials = nil
    if self.effectMaterial then
        InsMaterials = self.effectMaterial:instantiate()
    else
        InsMaterials = rendermaterial.material
    end
    materials:pushBack(InsMaterials)
    self.materials = materials
    rendermaterial.materials = self.materials

    return rendermaterial.material
end

function TextAnim:initAnimConfig()
    self.text:forceTypeSetting()
	self.count = self.text.chars:size()
    for i = 0, self.text.chars:size() - 1 do
        local char = self.text.chars:get(i)
        if char.utf8code == "\n" or char.utf8code == " " then
            self.count = self.count - 1
        end
    end
	self.CharForward = 0.96  --zi yu zi zhi jian de jian ge, fan wei shi [0, 1]
	self.CharDuration = 1.0 / (self.count - self.CharForward * (self.count - 1.0))
	self.CharForward = self.CharForward * self.CharDuration
    self.charAnchor = {}
    self.index = {}
    self.perRowSize = {}
    for i = 0, self.text.chars:size() - 1 do
        local char = self.text.chars:get(i)
        if char.utf8code ~= "\n" then
            if self.perRowSize[char.rowth] == nil then
                self.perRowSize[char.rowth] = 1
            else
                self.perRowSize[char.rowth] = self.perRowSize[char.rowth] + 1
            end
        end
    end
    local j = 0
    for i = 0, self.text.chars:size() - 1 do 
        local char = self.text.chars:get(i)
        if char.utf8code ~= "\n" and char.utf8code ~= " " then
            local x = char.idInRow + 1
            local y = self.perRowSize[char.rowth] - x - 1 + 2
            x = math.max(math.random(-x, -1), -3)
            y = math.min(math.random(1, y), 3)
            if char.idInRow % 2 == 0 then
                self.charAnchor[j] = char.width * y * 0.75
            else
                self.charAnchor[j] = char.width * x * 0.75
            end
            self.index[j] = i
            j = j + 1
        end
    end
    for i = 0, self.count - 1 do
        local a = math.floor(math.random(0, self.count - 1))
        local b = math.floor(math.random(0, self.count - 1))

        local temp = self.index[a]
        self.index[a] = self.index[b]
        self.index[b] = temp

        temp = self.charAnchor[a]
        self.charAnchor[a] = self.charAnchor[b]
        self.charAnchor[b] = temp
    end
end

function TextAnim:onUpdate(comp, deltaTime)
    if Amaz.Macros and Amaz.Macros.EditorSDK then
        self:seek(self.curTime)
        if self.autoPlay then
            self.curTime = self.curTime + deltaTime
            self.progress = (self.curTime % self.duration) / self.duration
        end
    else
    end


end




function TextAnim:addEffectLayers(i)
	if self.text.effectTextParam ~= nil then
    	self.effectLayers = self.text.effectTextParam.effectLayers
	else
		return 
	end
	self.cloneEffectParams[i] = self.cloneEntity[i]:getComponent("SDFText").effectTextParam
	if self.cloneEffectParams[i] ~= nil and self.effectLayers ~= nil then
		self.cloneEffectLayers[i] = self.cloneEffectParams[i].effectLayers
		for j = 0, self.cloneEffectLayers[i]:size() - 1 do 
			if j < self.effectLayers:size() then
				self.cloneEffectLayers[i]:get(j).mat = self.effectLayers:get(j).mat
				self.cloneEffectLayers[i]:get(j).texture = self.effectLayers:get(j).texture
			end
		end
	end
end

function TextAnim:addEntity(i)
	self.cloneEntity[i] = self.textEntity.scene:createEntity("sdf"..i)
	self.cloneEntity[i]:addComponent("Transform")
	self.ctrans[i] = self.cloneEntity[i]:getComponent("Transform")
	self.ctrans[i].localPosition = Amaz.Vector3f(0.0, 0.0, -10.0)
	self.ctrans[i].localScale = Amaz.Vector3f(1, 1, 1.0)
	-- self.cloneEntity[i]:cloneComponentOf(self.text)
	self.cloneEntity[i]:cloneComponentOf(self.text1)
    local sdf = self.cloneEntity[i]:addComponent("SDFText")
    sdf:setTextWrapper(self.cloneEntity[i]:getComponent("Text"))
	self.cloneEntity[i]:cloneComponentOf(self.renderer)
	self.ctrans[i].parent = self.parentTrans
	self.parentTrans.children:pushBack(self.ctrans[i])
	self:addEffectLayers(i)
end

function TextAnim:getTextFontSize(comp)
    local text = self.text1
    -- local textColor = Amaz.Vector3f(1.0,1.0,1.0)
    local fontSize = 32
    if text then 
        
        if text.forceFlushCommandQueue then
            text:forceFlushCommandQueue()
        end
        local letters = text.letters
        if letters:size() > 0 then
            local letter0 = letters:get(0)
            fontSize = letter0 and letter0.letterStyle and letter0.letterStyle.fontSize
        end
    else
        fontSize = self.text.fontSize
    end
    return fontSize
end
function TextAnim:seek(time)
    local w = Amaz.BuiltinObject:getInputTextureWidth()
    local h = Amaz.BuiltinObject:getInputTextureHeight()
    local r = math.min(w / h, 1.0)
    local chars = self.text.chars
    self.ofs = Amaz.Vector2f(0, 0)
    for i = 0, chars:size() - 1, 1 do
        local char = chars:get(i)
        if char.utf8code == "\n" then
            break
        end
        local x = char.initialPosition.x / w * 2.0
        local y = char.initialPosition.y / h * 2.0
        self.ofs = Amaz.Vector2f(x * r, y * r)
    end
    if self.first == true then
        self:initKeyFrame()
        --self:initAnimConfig()
        self.text.targetRTExtraSize = Amaz.Vector2f(0.0, self.text.rect.height * 3.0)
	    self.text.renderToRT = true
        self.material[1] = self:setMatToSDFText(self.text, self.renderer)
        self.renderer.sortingOrder = 1
        self.text:forceTypeSetting()
        self.text.targetRTExtraSize = Amaz.Vector2f(0.0, 0.0)


        self.rowNum = 1
        local c = 0
        self.cNum = 0
        for i = 0, chars:size() - 1, 1 do
            local char = chars:get(i)
            if char.utf8code == "\n" then
                self.rowNum = self.rowNum + 1
                self.cNum = math.max(c, self.cNum)
                c = 1
            else
                c = c + 1
            end
        end

        self.cNum = math.max(c, self.cNum)
        self.CharForward = {0, 0.8444, 0.89}
        local averageForward = 0.0
        for i = 1, #self.CharForward do
            averageForward = averageForward + self.CharForward[i]

        end
        averageForward = averageForward / (#self.CharForward - 1)
        -- self.CharForward = 0.85  --zi yu zi zhi jian de jian ge, fan wei shi [0, 1]
        self.CharDuration = 1.0 / (#self.CharForward - averageForward * (#self.CharForward - 1.0))
        -- self.CharForward = self.CharForward * self.CharDuration
        for i = 1, #self.CharForward do
            self.CharForward[i] = self.CharForward[i] * self.CharDuration
        end
        self.first = false
    else
    end



    if Amaz.Macros and Amaz.Macros.EditorSDK then
    else
        self.progress = math.mod(time / self.duration, 1.0)
    end
    local perScale = {1, 0.9, 0.8, 0.7, 0.6}
    


    local CharForward = 0.0
    local size = self:getTextFontSize(self.text) / 32 * 720 / math.min(w, h)
    for i = 1, 3 do 
        CharForward = CharForward + self.CharForward[i]
        local s = util.clamp(0, self.CharDuration, self.progress - (i - 1) * self.CharDuration + CharForward)
        local progress = util.remap01(0, self.CharDuration, s)
        local Position_X = self.Position_X:getCurPartVal(progress)
        local Position_Y = self.Position_Y:getCurPartVal(progress)
        local Scale = self.Scale:getCurPartVal(progress)
        local Rotate = self.Rotate:getCurPartVal(progress)
        local AnchorRotate = -self.AnchorRotate:getCurPartVal(progress)
        self.material[1]:setVec2("u_Ofs_"..i, Amaz.Vector2f((Position_X * 0.001 * size + 0.125 * (i - 1) * size) * r, (-Position_Y * 0.001 * size + 0.035 * (i - 1) * size * perScale[i]) * r))
        self.material[1]:setFloat("u_Angle_"..i, -Rotate - (i - 1) * 5.)
        self.material[1]:setFloat("u_Scale_"..i, Scale * 0.01 * perScale[i])
        local s = Scale * 0.01 * size
        local Anchor_X = self.Anchor_X:getCurPartVal(progress)
        local Anchor_Y = self.Anchor_Y:getCurPartVal(progress)
        local AnchorScale = self.AnchorScale:getCurPartVal(progress) * 0.01
        local Alpha = util.clamp(0.0, 1.0, util.remap01(0.0, 0.05, progress))
        local ofsx = (Anchor_X * 0.001 * 2.0 - 1.0) * s * r
        local ofsy = (Anchor_Y * 0.001 * 2.0 - 1.0) * s * r
        -- for i = 1, 4 do
        self.material[1]:setVec2("u_Anchor_"..i, self.ofs)
        self.material[1]:setVec2("u_Anchor1_"..i, Amaz.Vector2f(-ofsx, ofsy))
        self.material[1]:setFloat("u_AnchorAngle_"..i, AnchorRotate)
        self.material[1]:setFloat("u_AnchorScale_"..i, AnchorScale)
        self.material[1]:setFloat("u_Alpha_"..i, Alpha)
    end
    self.trans.localPosition = Amaz.Vector3f(0.28 * size * r + (1.0 - r) * 0.05, -0.7 * size * r, self.trans.localPosition.z)
    self.material[1]:setFloat("u_AllAlpha", (1. - math.pow(util.clamp(0.0, 1.0, util.remap01(0.7, 0.8, self.progress)), 0.5)))
end


function TextAnim:onEnter()
	self.first = true
	
end
function TextAnim:resetData( ... )
	if self.text ~= nil then
    	local chars = self.text.chars 
		for i = 1, self.text.chars:size() do
			local char = chars:get(i - 1)
			if char.rowth ~= -1 then
				char.position = char.initialPosition
				char.rotate = Amaz.Vector3f(0, 0, 0)
				char.scale = Amaz.Vector3f(1, 1, 1)
				char.color = Amaz.Vector4f(1, 1, 1, 1)
			end
		end
        self.text.renderToRT = false
        self.text.chars = chars
	end

    self.renderer.sortingOrder = self.sortNumber
	self.trans.localPosition = Amaz.Vector3f(0, 0, 0)
	self.trans.localEulerAngle = Amaz.Vector3f(0, 0, 0)
	self.trans.localScale = Amaz.Vector3f(1, 1, 1)
    self.text.targetRTExtraSize = Amaz.Vector2f(0.0, 0.0)

    -- if self.customEntity ~= nil then
    --     self.text.entity.scene:removeEntity(self.customEntity)
    --     self.camera.children:erase(self.customEntity)
    --     self.customEntity = nil
    -- end
    -- self.text.entity.layer = 0
end

function TextAnim:setDuration(duration)
   self.duration = duration
end
function TextAnim:onLeave()
	self:resetData()
	self.first = true
end
function TextAnim:clear()
	self:resetData()

end

exports.TextAnim = TextAnim
return exports
