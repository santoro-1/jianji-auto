local AETools = AETools or {}     ---@class AETools
AETools.__index = AETools

function AETools:new(attrs)
    local self = setmetatable({}, AETools)
    self.attrs = attrs

    local max_frame = 0
    for _,v in pairs(attrs) do
        for i = 1, #v do
            local content = v[i]
            local cur_frame = content[2][2]
            max_frame = math.max(cur_frame, max_frame)
        end
    end
    self:SetAllFrame(max_frame)

    return self
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

function AETools:SetAllFrame(val)
    self.all_frame = val
end

function AETools:GetVal(_name, _progress)
    local content = self.attrs[_name]
    if content == nil then
        return nil
    end

    local cur_frame = _progress * self.all_frame

    for i = 1, #content do
        local info = content[i]
        local start_frame = info[2][1]
        local end_frame = info[2][2]
        if cur_frame >= start_frame and cur_frame < end_frame then
            local cur_progress = self._remap01(start_frame, end_frame, cur_frame)
            local bezier = info[1]
            local value_range = info[3]

            local p = self:_cubicBezier01(bezier, cur_progress)

            if type(value_range[1]) == "table" then
                local res = {}
                for j = 1, #value_range[1] do
                    res[j] = self._mix(value_range[1][j], value_range[2][j], p)
                end
                return res
            end
            return self._mix(value_range[1], value_range[2], p)
        end
    end

    local first_info = content[1]
    local start_frame = first_info[2][1]
    if cur_frame<start_frame then
        return first_info[3][1]
    end

    local last_info = content[#content]
    local end_frame = last_info[2][2]
    if cur_frame>=end_frame then
        return last_info[3][2]
    end

end

function AETools:test()
    Amaz.LOGI("lrc "..tostring(self.key_frame_info), tostring(#self.key_frame_info))
end


local util = nil ---@class Util

local exports = exports or {}
local TextAnim = TextAnim or {}
TextAnim.__index = TextAnim
---@class TextAnim : ScriptComponent
---@field autoplay boolean
---@field duration number
---@field curTime number
---@field progress number [UI(Range={0, 1}, Slider)]

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


local function getRootDir()
    local rootDir = nil
    if rootDir == nil then
        local str = debug.getinfo(2, "S").source
        rootDir = str:match("@?(.*/)")
    end
    return rootDir
end

local ae_attribute = {
	["ADBE_Radial_Blur_0001_0_0"]={
		{{0.166666667, 0.166666667, 0.833333333, 0.833333333, }, {0, 8.000008, }, {{35, }, {0, }, }, }, 
	}, 
	["ADBE_Scale_0_1"]={
		{{0.166666667,0.166666667, 0.66666667, 1, }, {0, 10.00001, }, {{15, 15, 100, }, {110, 110, 100, }, }, }, 
		{{0.33333333,0, 0.833333333,0.833333333, }, {10.00001, 16.000016, }, {{110, 110, 100, }, {100, 100, 100, }, }, }, 
	}, 
	["ADBE_Radial_Blur_0001_1_2"]={
		{{0.166666667, 0.166666667, 0.833333333, 0.833333333, }, {0, 8.000008, }, {{35, }, {0, }, }, }, 
		{{0.166666667, 0.166666667, 0.833333333, 0.833333333, }, {8.000008, 10.00001, }, {{0, }, {54, }, }, }, 
		{{0.166666667, 0.166666667, 0.833333333, 0.833333333, }, {10.00001, 30.000031, }, {{54, }, {0, }, }, }, 
	}, 
	["ADBE_Scale_1_3"]={
		{{0.166666667,0.166666667, 0.66666667, 1,}, {0, 10.00001, }, {{15, 15, 100, }, {110, 110, 100, }, }, }, 
		{{0.026666635, 0,0,1,}, {10.00001, 30.000031, }, {{110, 110, 100, }, {180, 180, 100, }, }, }, 
	}, 
	["ADBE_Opacity_1_4"]={
		{{0.166666667, 0.166666667, 0.66666667, 1, }, {10.00001, 30.000031, }, {{100, }, {0, }, }, }, 
	}, 
}

function TextAnim.new(construct, ...)
    local self = setmetatable({}, TextAnim)

    -- online attr
    self.duration = 0
    self.curTime = 0

    self.sharedMaterial = nil
	self.materials = nil
    self.renderer = nil
    self.isVertical = 0.0
    self.first = true

    -- Editor about ---
    self.autoplay = false
    self.duration = 2

    -- Runtime ---
    self.progress = 0

    -- Init Attr ----

    if construct and TextAnim.constructor then TextAnim.constructor(self, ...) end
    return self
end



function TextAnim:constructor()

end

function TextAnim:transInitial(trans)
    if trans then
        trans.localPosition = Amaz.Vector3f(0,0,0)
        trans.localScale = Amaz.Vector3f(1,1,1)
        trans.localEulerAngle = Amaz.Vector3f(0,0,0)
    end
end

function TextAnim:onStart(comp)
    util.registerRootDir(getRootDir())
    self.entity = comp.entity
	self.text = comp.entity:getComponent("SDFText")
    if self.text == nil then
        local text = comp.entity:getComponent('Text')
        if text ~= nil then
			self.text = comp.entity:addComponent('SDFText')
            self.text:setTextWrapper(text)
        end
    end
    self.trans = comp.entity:getComponent("Transform")
	self.transParent = self.trans.parent

    self.renderer = nil
	if self.text ~= nil then
		self.renderer = comp.entity:getComponent("MeshRenderer")
	else
		self.renderer = comp.entity:getComponent("Sprite2DRenderer")
	end

    self:transInitial(self.trans)

    self.first = true

    self.attrs = AETools:new(ae_attribute)

end

function TextAnim:initAnim()
    self.text.renderToRT = true
    local materials = Amaz.Vector()
    local InsMaterials = nil
    if self.sharedMaterial then
        InsMaterials = self.sharedMaterial:instantiate()
    else
        InsMaterials = self.renderer.material
    end
    materials:pushBack(InsMaterials)
    self.materials = materials
    self.renderer.materials = self.materials

    -- if Amaz.Macros and Amaz.Macros.EditorSDK then
    -- else
    --     self:ReadFromJson()
    -- end
end


function TextAnim:onUpdate(comp, time)
    if Amaz.Macros and Amaz.Macros.EditorSDK then
        self.curTime = self.curTime + time
        self:seek(self.curTime)
    end
end

---@function [UI(Button="generate json file")]
function TextAnim:CreateJsonFile()
    Amaz.LOGI("lrc", "CreateJsonFile")
    for k,v in pairs(util.getRegistedParams()) do
        if self[k] == nil then
            Amaz.LOGE("lrc ERROR!!!", "no registed value called : "..tostring(k))
        else
            util.setRegistedVal(k, self[k])
        end
    end
    util.CreateJsonFile("data_val.json")
end

---@function [UI(Button="read from json file")]
function TextAnim:ReadFromJson()
    Amaz.LOGI("lrc readfrom json", "read from json")
    local t = util.ReadFromJson("data_val.json")
    for k,v in pairs(t) do 
        self[k] = v
    end
end

function TextAnim:seek(time)
    
    if self.first and self.text.chars:size() > 0 then
        self:initAnim()
        self.first = false
    end

    if Amaz.Macros and Amaz.Macros.EditorSDK then
        if self.autoplay then
            self.progress = time % self.duration / self.duration
        end
    else
        self.progress = time % (self.duration+0.00001) / (self.duration+0.00001)
        if self.progress > 1 then
            self.progress = 1
        end
    end

    if self.text and self.text.chars:size() > 0 then

        if Amaz.Macros and Amaz.Macros.EditorSDK then
        else
        end

        local rect = self.text.rect

        -- self.progress = math.floor(self.progress*30)/30
        local s1 = self.attrs:GetVal("ADBE_Scale_0_1", self.progress)
        local b1 = self.attrs:GetVal("ADBE_Radial_Blur_0001_0_0", self.progress)
        self.renderer.material:setFloat("s1", s1[1] * 0.01)

        local b_a = 1
        self.renderer.material:setFloat("b1", b1[1] * b_a)
        -- Amaz.LOGI("lrc "..self.progress*30, tostring(b1[1]))
        
        
        local s2 = self.attrs:GetVal("ADBE_Scale_1_3", self.progress)
        -- Amaz.LOGI("lrc "..self.progress*30, tostring(s2[1]))
        local b2 = self.attrs:GetVal("ADBE_Radial_Blur_0001_1_2", self.progress)
        local a2 = self.attrs:GetVal("ADBE_Opacity_1_4", self.progress)
        self.renderer.material:setFloat("s2", s2[1] * 0.01)
        self.renderer.material:setFloat("b2", b2[1] * b_a)
        self.renderer.material:setFloat("a2", a2[1] * 0.01)

        self.renderer.material:setVec2("textSize", Amaz.Vector2f(rect.width, rect.height))
    end

end

function TextAnim:resetData()
    if self.text and self.text.chars:size() > 0 then
        self:transInitial(self.trans)
        for i = 1, self.text.chars:size() do
            local char = self.text.chars:get(i-1)
            char.position = char.initialPosition
            char.rotate = Amaz.Vector3f(0,0,0)
            char.scale = Amaz.Vector3f(1,1,1)
            char.color = Amaz.Vector4f(1,1,1,1)
        end
        self.text.renderToRT = false
    end
end


function TextAnim:setDuration(duration)
    self.duration = duration
end

function TextAnim:clear()
    self:resetData()
end


function TextAnim:onEnter()
    EffectSdk.LOG_LEVEL(8, "lrc onEnter ========>>")
    self:resetData()
    self.first = true
end

function TextAnim:onLeave()
    EffectSdk.LOG_LEVEL(8, "lrc onLeave ========>>")
    self:resetData()
    self.first = true
end

exports.TextAnim = TextAnim
return exports
