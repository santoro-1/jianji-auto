local util = nil ---@class Util
local AETools = nil ---@class AETools

local exports = exports or {}
local TextAnim = TextAnim or {}
TextAnim.__index = TextAnim
---@class TextAnim : ScriptComponent
---@field autoplay boolean
---@field duration number
---@field curTime number
---@field progress number [UI(Range={0, 1}, Slider)]
---@field single_line_anim_time number
---@field single_char_anim_time number
---@field move_bezier Vector4f
---@field rotate_bezier Vector4f

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
    self.single_char_anim_time = 0.5
    self.single_line_anim_time = 0.8
    self.move_bezier = Amaz.Vector4f(.16,.84,.44,1)
    self.rotate_bezier = Amaz.Vector4f(.16,.84,.44,1)

    self:registerParams("move_bezier", "vec4")
    self:registerParams("rotate_bezier", "vec4")
    self:registerParams("single_char_anim_time", "float")
    self:registerParams("single_line_anim_time", "float")

    if construct and TextAnim.constructor then TextAnim.constructor(self, ...) end
    return self
end

function TextAnim:registerParams(_name, _type)
    local _data = self[_name]
    -- if util == nil then
    --     util = includeRelativePath("Util")
        util.registerRootDir(getRootDir())
    -- end
    util.registerParams(_name, _data, _type)
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
    -- if util == nil then
    --     util = includeRelativePath("Util")
        util.registerRootDir(getRootDir())
    -- end
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

end

function TextAnim:initAnim()
    self.text.renderToRT = false
    -- local materials = Amaz.Vector()
    -- local InsMaterials = nil
    -- if self.sharedMaterial then
    --     InsMaterials = self.sharedMaterial:instantiate()
    -- else
    --     InsMaterials = self.renderer.material
    -- end
    -- materials:pushBack(InsMaterials)
    -- self.materials = materials
    -- self.renderer.materials = self.materials

    if Amaz.Macros and Amaz.Macros.EditorSDK then
    else
        self:ReadFromJson()
    end

    -- local w = Amaz.BuiltinObject.getOutputTextureWidth()
    -- local h = Amaz.BuiltinObject.getOutputTextureHeight()

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

function TextAnim:updateLines()
    self.char_info = {}
    local cur_line = 1
    for i = 1, self.text.chars:size() do
        local char = self.text.chars:get(i-1)
        local idInRow = char.idInRow
        if idInRow == -1 then
            cur_line = cur_line + 1
        else
            if self.char_info[cur_line] == nil then
                self.char_info[cur_line] = {}
            end
            self.char_info[cur_line][#self.char_info[cur_line]+1] = char
        end
    end
end

function TextAnim:v2t(v)
    return {v.x, v.y, v.z, v.w}
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
        self:updateLines()

        local lines = #self.char_info
        local slat = self.single_line_anim_time

        for i = 1, lines do
            local chars = self.char_info[i]
            local char_count = #chars

            local line_ps = (1-slat)*((i-1)/(lines-1))
            local line_p = util.remap01(line_ps, line_ps + slat, self.progress)

            if lines == 1 then
                line_p = util.remap01(0, 1, self.progress)
                slat = 0.5
            end

            for j = 1, char_count do
                local char = chars[j]

                local scat = self.single_char_anim_time
                local p_s = (1-scat)*util.bezier({.72,.15,1,1})(((j-1)/(char_count-1)), 0, 1, 1)
                -- Amaz.LOGI("lrc "..j, p_s)
                local p = util.remap01(p_s, p_s + scat, line_p)

                if char_count == 1 then
                    p = util.remap01(0, 1, line_p)
                end

                local pos = char.initialPosition
                if self.text.typeSettingKind == 0 then
                    char.position = Amaz.Vector3f(
                        util.mix(pos.x + rect.width * 1, pos.x, util.bezier(self:v2t(self.move_bezier))(p, 0, 1, 1)),
                        pos.y, pos.z
                    )

                    local cur_x = char.position.x
                    local target_x = char.initialPosition.x

                    local cur_x_p = math.abs(cur_x-target_x)/rect.width
                    local alpha_ps = (rect.width * 0.5 - pos.x)/rect.width
                    -- local alpha_p = 1-util.remap01(alpha_ps-0.4<0 and 0 or (alpha_ps-0.4), alpha_ps, cur_x_p)
                    local alpha_p = 1-util.remap01(alpha_ps-0.4, alpha_ps, cur_x_p)
                    if alpha_ps - 0.4 < 0 then
                        alpha_p = 1-util.remap01(0, 0.4 * 0.5, cur_x_p)
                    end
                    local col = char.color
                    char.color = Amaz.Vector4f(col.x, col.y, col.z, alpha_p)
                else
                    char.position = Amaz.Vector3f(
                        pos.x,
                        util.mix(pos.y - rect.height * 1, pos.y, util.bezier(self:v2t(self.move_bezier))(p, 0, 1, 1)),
                        pos.z
                    )

                    local cur_y = char.position.y
                    local target_y = char.initialPosition.y

                    local cur_y_p = math.abs(cur_y-target_y)/rect.height
                    -- Amaz.LOGI("lrc "..j, cur_y_p)
                    local alpha_ps = (rect.height * 0.5 + pos.y)/rect.height
                    local alpha_p = 1-util.remap01(alpha_ps-0.4, alpha_ps, cur_y_p)
                    if alpha_ps - 0.4 < 0 then
                        alpha_p = 1-util.remap01(0, 0.4 * 0.5, cur_y_p)
                    end
                    -- local alpha_p = 1-util.remap01(alpha_ps-0.4<0 and 0 or (alpha_ps-0.4), alpha_ps, cur_y_p)
                    local col = char.color
                    char.color = Amaz.Vector4f(col.x, col.y, col.z, alpha_p)
                end



                char.rotate = Amaz.Vector3f(
                    0,0,
                    util.mix(0, 360, util.bezier(self:v2t(self.rotate_bezier))(p, 0, 1, 1))
                )
            end

            -- self.materials:get(0):setVec2("text_size", Amaz.Vector2f(
            --     rect.width, rect.height
            -- ))

        end

        -- local blur_progress = util.remap01(0., 1., self.progress)
        -- self.materials:get(0):setFloat("blur_progress", blur_progress)

        -- self.materials:get(0):setFloat("typeSettingKind", self.text.typeSettingKind)

        -- local mainTex = self.materials:get(0):getTex("_MainTex")
        -- if mainTex then
        --     local render_size = Amaz.Vector2f(mainTex.width, mainTex.height)
        --     local text_size = Amaz.Vector2f(rect.width, rect.height)
        --     local cut_size_x = 0
        --     local cut_size_y = 0
        --     if text_size.x < render_size.x then
        --         cut_size_x = (render_size.x - text_size.x)/render_size.x * 0.5
        --     end
        --     if text_size.y < render_size.y then
        --         cut_size_y = (render_size.y - text_size.y)/render_size.y * 0.5
        --     end
        --     local cut_size = Amaz.Vector2f(cut_size_x, cut_size_y)
        --     self.materials:get(0):setVec2("cut_size", cut_size)
        -- end
        -- -- Amaz.LOGI("lrc", tostring(Amaz.Vector2f(mainTex.width, mainTex.height)))
        -- self.materials:get(0):setFloat("typeSettingKind", self.text.typeSettingKind)
        -- self.materials:get(0):setFloat("backgroundEnabled", self.text.backgroundEnabled and 1 or 0)
    end

    -- EffectSdk.LOG_LEVEL(8, "lrc ========>> seek: "..time)
    -- EffectSdk.LOG_LEVEL(8, "lrc ========>> progress: "..self.progress)
    -- EffectSdk.LOG_LEVEL(8, "lrc ========>> duration: "..self.duration)
end

function TextAnim:resetData()
    if self.text and self.text.chars:size() > 0 then
        self:transInitial(self.trans)
        for i = 1, self.text.chars:size() do
            local char = self.text.chars:get(i-1)
            char.position = char.initialPosition
            char.rotate = Amaz.Vector3f(0,0,0)
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
    self:resetData()
    self.first = true
end

function TextAnim:onLeave()
    self:resetData()
    self.first = true
end

exports.TextAnim = TextAnim
return exports
