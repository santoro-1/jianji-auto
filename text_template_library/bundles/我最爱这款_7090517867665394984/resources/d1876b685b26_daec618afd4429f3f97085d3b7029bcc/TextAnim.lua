local util = nil ---@class Util

local exports = exports or {}
local TextAnim = TextAnim or {}
TextAnim.__index = TextAnim
---@class TextAnim : ScriptComponent
---@field split_line1 string
---@field autoplay boolean
---@field isShaking boolean
---@field isTypesetting boolean
---@field duration number
---@field split_line2 string
---@field curTime number
---@field progress number [UI(Range={0, 1}, Slider)]
---@field split_line3 string
---@field trapezoid Vector4f
---@field shakeXRange Vector3f
---@field shakeYRange Vector3f
---@field shakeZRange Vector3f
---@field shakeFrequency Vector2f
---@field moveXRange Vector2f
---@field moveYRange Vector2f
---@field moveFrequency Vector2f
---@field camera_fov number
---@field selfZ number
---@field selfRotate Vector3f
---@field showingInfo Vector4f
---@field showingBezier Vector4f
---@field blurStep number

local function getRootDir()
    local rootDir = nil
    if rootDir == nil then
        local str = debug.getinfo(2, "S").source
        rootDir = str:match("@?(.*/)")
    end
    -- Amaz.LOGI("lrc getRootDir 3", tostring(rootDir))
    return rootDir
end

function TextAnim.new(construct, ...)
    local self = setmetatable({}, TextAnim)
    self.sharedMaterial = nil
	self.materials = nil
    self.renderer = nil
    self.isVertical = 0.0
    self.duration = 0
    self.first = true
    self.lasttime = 0.0
    self.length = 0.45

    -- Editor about ---
    self.autoplay = false
    self.isShaking = true
    self.isTypesetting = true
    self.duration = 2
    self.split_line1 = "----- Editor About -----"
    self.split_line2 = "----- Runtime -----"
    self.split_line3 = "Init Attr"

    -- Runtime ---
    self.curTime = 0
    self.progress = 0

    -- Init Attr ----
    self.trapezoid = Amaz.Vector4f(0.8, 1.5, 0,0)
    self.shakeXRange = Amaz.Vector3f(-10, 10, 0.5)
    self.shakeYRange = Amaz.Vector3f(-15, 15, 0.5)
    self.shakeZRange = Amaz.Vector3f(-30, 30, 0.5)
    self.shakeFrequency = Amaz.Vector2f(6, 0.5)

    self.moveXRange = Amaz.Vector2f(0.2, 0.5)
    self.moveYRange = Amaz.Vector2f(0.2, 0.5)
    self.moveFrequency = Amaz.Vector2f(6, 0.5)

    self.camera_fov = 60
    self.selfZ = 0
    self.selfRotate = Amaz.Vector3f(0,0,0)

    self.showingInfo = Amaz.Vector4f(0, 0.2, 0.8, 1)
    self.showingBezier = Amaz.Vector4f(0.16, 0.84, 0.43, 1.11)

    self.blurStep = 1

    self:registerParams("trapezoid", Amaz.Vector4f(0.8, 1.5, 0,0), "vec4")
    self:registerParams("shakeXRange", Amaz.Vector3f(-15, 15, 0.5), "vec3")
    self:registerParams("shakeYRange", Amaz.Vector3f(-15, 15, 0.5), "vec3")
    self:registerParams("shakeZRange", Amaz.Vector3f(-15, 15, 0.5), "vec3")
    self:registerParams("shakeFrequency", Amaz.Vector2f(6, 0.5), "vec2")

    self:registerParams("moveXRange", Amaz.Vector2f(0.2, 0.5), "vec2")
    self:registerParams("moveYRange", Amaz.Vector2f(0.2, 0.5), "vec2")
    self:registerParams("moveFrequency", Amaz.Vector2f(6, 0.5), "vec2")


    self:registerParams("camera_fov", 60, "float")
    self:registerParams("selfZ", 0, "float")

    self:registerParams("selfRotate", Amaz.Vector3f(0,0,0), "vec3")
    self:registerParams("showingInfo", Amaz.Vector4f(0, 0.2, 0.8, 1), "vec4")

    self:registerParams("showingBezier", Amaz.Vector4f(0.16, 0.84, 0.43, 1.11), "vec4")
    self:registerParams("blurStep", -0.3, "float")

    if construct and TextAnim.constructor then TextAnim.constructor(self, ...) end
    return self
end

function TextAnim:registerParams(_name, _data, _type)
    self[_name] = _data
    if util == nil then
        util = includeRelativePath("Util")
        util.registerRootDir(getRootDir())
    end
    util.registerParams(_name, _data, _type)
end

function TextAnim:constructor()

end

function TextAnim:onStart(comp) 
    if util == nil then
        util = includeRelativePath("Util")
        util.registerRootDir(getRootDir())
    end

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

    self.first = true
    Amaz.LOGE("lrc onStart", "onStart")
end

function TextAnim:resetCharLineInfo()

    self.charInfo = {}
    for i=1, self.text.chars:size() do
        local char = self.text.chars:get(i-1)
        self.charInfo[#self.charInfo + 1] = {
            ["char"] = char,
            ["ori_pos"] = char.initialPosition:copy(),
            ["ori_scale"] = Amaz.Vector3f(1,1,1),
            ["ori_rot"] = Amaz.Vector3f(0,0,0),
            ["cur_pos"] = char.initialPosition:copy(),
            ["cur_scale"] = Amaz.Vector3f(1,1,1),
            ["cur_rot"] = Amaz.Vector3f(0,0,0),
        }
    end


    -- if self.charLineInfo == nil then
        self.charLineInfo = {}
        for i=1, self.text.chars:size() do
            local char = self.text.chars:get(i-1)
            local line = char.rowth + 1
            if self.charLineInfo[line] == nil then
                self.charLineInfo[line] = {}
            end
            self.charLineInfo[line][#self.charLineInfo[line] + 1] = {
                ["char"] = char,
                ["ori_pos"] = char.initialPosition:copy(),
                ["ori_scale"] = Amaz.Vector3f(1,1,1),
                ["ori_rot"] = Amaz.Vector3f(0,0,0),
                ["cur_pos"] = char.initialPosition:copy(),
                ["cur_scale"] = Amaz.Vector3f(1,1,1),
                ["cur_rot"] = Amaz.Vector3f(0,0,0),
                ["cur_idx"] = i
            }
        end
    -- end

    for line, chars in pairs(self.charLineInfo) do
        local gap = 0
        local count = #chars
        for i=count, 1, -1 do
            local char = chars[i]["char"]
            local ori_pos = chars[i]["ori_pos"]
            local ori_scale = chars[i]["ori_scale"]
            local cur_idx = chars[i]["cur_idx"]
            if self.text.typeSettingKind == 0 then
                chars[i]["cur_pos"] = Amaz.Vector3f(
                    ori_pos.x - gap,
                    ori_pos.y,
                    ori_pos.z
                )
                -- Amaz.LOGI("lrc gap "..tostring(i), gap)
                local scale_val = util.mix(self.trapezoid.x, self.trapezoid.y, (i-1)/count)
                local target_scale = Amaz.Vector3f(scale_val * ori_scale.x, scale_val * ori_scale.y, scale_val * ori_scale.z)
                -- local next_scale_val = util.mix(self.trapezoid.x, self.trapezoid.y, i/count)
                -- local next_target_scale = Amaz.Vector3f(next_scale_val * ori_scale.x, next_scale_val * ori_scale.y, next_scale_val * ori_scale.z)
                gap = gap + (target_scale.x - ori_scale.x) * char.width * 0.55
            else
                chars[i]["cur_pos"] = Amaz.Vector3f(
                    ori_pos.x,
                    ori_pos.y - gap,
                    ori_pos.z
                )
                local scale_val = 1
                local target_scale = Amaz.Vector3f(scale_val * ori_scale.x, scale_val * ori_scale.y, scale_val * ori_scale.z)
                gap = gap + (target_scale.y - ori_scale.y) * char.height * 0.55
            end
            self.charInfo[cur_idx]["cur_pos"] = chars[i]["cur_pos"]
        end
    end
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

    self.oriTexInfo = { }
    for i = 1, self.text.chars:size() do
        local char = self.text.chars:get(i-1)
        if self.oriTexInfo[i] == nil then
            self.oriTexInfo[i] = {}
        end
        self.oriTexInfo[i]["pos"] = char.position
        self.oriTexInfo[i]["rotate"] = char.rotate
        self.oriTexInfo[i]["scale"] = char.scale
    end
    self.oriTexInfo["trans_euler"] = self.trans.localEulerAngle


    if Amaz.Macros and Amaz.Macros.EditorSDK then
    else
        self:ReadFromJson()
    end

    self:resetCharLineInfo()
end

local function randVal(val, perc)
    return math.random() * val * perc + val * (1-perc)
end

---@function [UI(Button="generate shake info")]
function TextAnim:generateShakeInfo()
    math.randomseed(os.time())
    self.charShakeInfo = {}
    for i=1, self.text.chars:size() do
        self.charShakeInfo[#self.charShakeInfo + 1] = {
            ["rotate"] = {
                ["x"] = Amaz.Vector2f(randVal(self.shakeXRange.x, self.shakeXRange.z), randVal(self.shakeXRange.y, self.shakeXRange.z)),
                ["y"] = Amaz.Vector2f(randVal(self.shakeYRange.x, self.shakeYRange.z), randVal(self.shakeYRange.y, self.shakeYRange.z)),
                ["z"] = Amaz.Vector2f(randVal(self.shakeZRange.x, self.shakeZRange.z), randVal(self.shakeZRange.y, self.shakeZRange.z)),
                ["f"] = randVal(self.shakeFrequency.x, self.shakeFrequency.y)
            },
            ["move"] = {
                ["x"] = randVal(self.moveXRange.x, self.moveXRange.y),
                ["y"] = randVal(self.moveYRange.x, self.moveYRange.y),
                ["f"] = randVal(self.moveFrequency.x, self.moveFrequency.y)
            },
        }
    end
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

function TextAnim:shakingLogic(progress)
    if self.lastCharCount == nil then
        self.lastCharCount = self.text.chars:size()
        self:generateShakeInfo()
    end

    if self.text.chars:size() ~= self.lastCharCount then
        self.lastCharCount = self.text.chars:size()
        self:generateShakeInfo()
    end

    for i=1, self.text.chars:size() do
        local char = self.text.chars:get(i-1)
        local info = self.charShakeInfo[i]

        local rotateInfo = info["rotate"]
        local rotate_curve = math.sin(progress * math.pi * 2 * rotateInfo["f"])
        char.rotate = Amaz.Vector3f(
            rotate_curve > 0 and rotate_curve * rotateInfo["x"].y or rotate_curve * -rotateInfo["x"].x,
            rotate_curve > 0 and rotate_curve * rotateInfo["y"].y or rotate_curve * -rotateInfo["y"].x,
            rotate_curve > 0 and rotate_curve * rotateInfo["z"].y or rotate_curve * -rotateInfo["z"].x
        )

        local moveInfo = info["move"]
        local move_curve = math.sin(progress * math.pi * 2 * moveInfo["f"])
        local move_val = char.width * moveInfo["x"]
        local pos = char.position
        -- pos = self.charInfo[i]["cur_pos"]
        -- pos = char.initialPosition
        char.position = Amaz.Vector3f(
            pos.x + char.width * moveInfo["x"] * move_curve,
            pos.y + char.height * moveInfo["y"] * move_curve,
            pos.z
        )
        -- Amaz.LOGE("lrc char.width height "..i, tostring(Amaz.Vector2f(char.width, char.height)))
        -- Amaz.LOGE("lrc position "..i, tostring(char.position))

    end
end

function TextAnim:findCamera()
    if self.camera == nil then
        local entities = self.entity.scene.entities
        for i=1, entities:size() do
            local entity = entities:get(i-1)
            local comp = entity:getComponent("Camera")
            if comp ~= nil then
                self.camera = comp
                self.cameraTrans = entity:getComponent("Transform")
                self.camOriPos = self.cameraTrans:getWorldPosition()
                break
            end
        end
    end
    return self.camera, self.cameraTrans, self.camOriPos
end

function TextAnim:flyIn()
    local charCount = self.text.chars:size()
    local rect = self.text.rect
    local progress = util.remap01(self.showingInfo.x, self.showingInfo.y, self.progress)

    for line, chars in pairs(self.charLineInfo) do
        local count = #chars
        for i=count, 1, -1 do
            local char = chars[i]["char"]
            local ori_pos = chars[i]["ori_pos"]
            local ori_scale = chars[i]["ori_scale"]
            local cur_idx = chars[i]["cur_idx"]

            local cur_pos = chars[i]["cur_pos"]
            -- local scale_val = (self.trapezoid.y - self.trapezoid.x) * (i-1)/(count-1 + 0.001) + math.max(self.trapezoid.x, self.trapezoid.y)
            local scale_val = util.mix(self.trapezoid.x, self.trapezoid.y, i/count)
            if self.text.typeSettingKind == 1 then
                scale_val = util.mix(self.trapezoid.y, self.trapezoid.x, (i-1)/count)
            end
            char.scale = Amaz.Vector3f(scale_val * ori_scale.x, scale_val * ori_scale.y, scale_val * ori_scale.z)
            -- Amaz.LOGI("lrc "..i, tostring(char.scale))

            local pos = Amaz.Vector3f(
                util.mix(
                    -rect.width * 1.2, 
                    cur_pos.x, 
                    progress),
                util.mix(
                    ori_pos.y, 
                    cur_pos.y, 
                    progress),
                    cur_pos.z
            )
            char.position = pos

            self.charInfo[cur_idx]["cur_pos"] = pos

            local col = char.color
            char.color = Amaz.Vector4f(col.x, col.y, col.z, util.mix(0, 1, progress))
        end
    end
end

function TextAnim:flyOut()
    local charCount = self.text.chars:size()
    local rect = self.text.rect
    local progress = util.remap01(self.showingInfo.z, self.showingInfo.w, self.progress)

    self.materials:get(0):setFloat("leftFade", 1.2 * (progress))

    for line, chars in pairs(self.charLineInfo) do
        local count = #chars
        for i=1, count do
            local char = chars[i]["char"]
            local ori_pos = chars[i]["cur_pos"] == nil and chars[i]["ori_pos"] or chars[i]["cur_pos"]
            local ori_scale = chars[i]["ori_scale"]
            local cur_pos = chars[i]["cur_pos"]
            local cur_idx = chars[i]["cur_idx"]

            local pos = Amaz.Vector3f(
                util.mix(
                    -rect.width * 1.2, 
                    cur_pos.x, 
                    progress),
                util.mix(
                    ori_pos.y, 
                    cur_pos.y, 
                    progress),
                    cur_pos.z
            )
            char.position = pos
            self.charInfo[cur_idx]["cur_pos"] = pos

            local col = char.color
            char.color = Amaz.Vector4f(col.x, col.y, col.z, util.mix(1, 0, progress))
        end
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
        self.progress = time % self.duration / self.duration
    end



    if self.text and self.text.chars:size() > 0 then

        local rect = self.text.rect
        self.text.targetRTExtraSize = Amaz.Vector2f(0, rect.height)

        if self.text.fixedRectEnabled then
            if self.lastRectSize == nil or self.lastRectSize.width ~= rect.width or self.lastRectSize.height ~= rect.height then
                self.lastRectSize = rect
                self:resetCharLineInfo()
            end
        end

        if Amaz.Macros and Amaz.Macros.EditorSDK then
        else
            self.isShaking = true
            self.isTypesetting = true
        end
        -- typesetting logic
        if self.isTypesetting then
            local cam, camTrans, camOriPos = self:findCamera()
            
            local textPos = self.trans.localPosition
            -- camTrans.localPosition = Amaz.Vector3f(textPos.x, textPos.y, camOriPos.z)

            cam.type = 0
            
            cam.fovy = self.camera_fov
            self.materials:get(0):setMat4("myProj", cam.projectionMatrix)
            -- self.materials:get(0):setMat4("myView", camTrans.localMatrix:invert_Full())

            local pos = self.trans.localPosition
            self.trans.localEulerAngle = self.selfRotate
            self.trans.localPosition = Amaz.Vector3f(pos.x, pos.y, self.selfZ)

            cam.type = 1
            cam.zNear = 0.01
            cam.zFar = 1000

            -- camTrans:setWorldPosition(camOriPos)

            if self.progress < self.showingInfo.z then
                self:flyIn()
                self.materials:get(0):setFloat("progress", 1.-util.remap01(self.showingInfo.x, self.showingInfo.y, self.progress))
            else
                self:flyOut()
                self.materials:get(0):setFloat("progress", util.remap01(self.showingInfo.z, self.showingInfo.w, self.progress))
            end
        end

        -- shake logic
        if self.isShaking then
            local progress = util.remap01(self.showingInfo.y/2, 1, self.progress)
            self:shakingLogic(progress)
        else
            for i=1, self.text.chars:size() do
                local char = self.text.chars:get(i-1)
                char.rotate = Amaz.Vector3f(0,0,0)
            end
        end

        self.materials:get(0):setFloat("blurStep", self.blurStep)

        if self.progress < self.showingInfo.y then
            self.materials:get(0):setFloat("fade", (1-util.remap01(self.showingInfo.x, self.showingInfo.y, self.progress)) * 0.5)
            -- Amaz.LOGI("lrc", util.remap01(self.showingInfo.y, self.showingInfo.x, self.progress) * 0.5)
        elseif self.progress > self.showingInfo.z then
            self.materials:get(0):setFloat("fade", util.remap01(self.showingInfo.z, self.showingInfo.w, self.progress) * 0.5)
        else
            self.materials:get(0):setFloat("fade", 0)
        end

        if self.text.typeSettingKind == 0 then
            self.materials:get(0):setVec2("trapezoid", Amaz.Vector2f(self.trapezoid.z, self.trapezoid.w))
        else
            self.materials:get(0):setVec2("trapezoid", Amaz.Vector2f(-self.trapezoid.w, 0))
        end
    else

    end

    -- for i = 1, self.text.chars:size() do
    --     local char = self.text.chars:get(i-1)
    --     Amaz.LOGE("lrc position "..i, tostring(char.position))
    --     Amaz.LOGE("lrc init position "..i, tostring(char.initialPosition))
    -- end

end

function TextAnim:resetData()
    Amaz.LOGE("lrc resetData", 123)
    if self.text and self.text.chars:size() > 0 then
        Amaz.LOGE("lrc resetData", 3)
        for i=1, self.text.chars:size() do
            local char = self.text.chars:get(i-1)
            char.position = char.initialPosition
            char.rotate = Amaz.Vector3f(0,0,0)
            char.scale = Amaz.Vector3f(1,1,1)

            local col = char.color
            char.color = Amaz.Vector4f(col.x, col.y, col.z, 1)
        end
        self.text.targetRTExtraSize = Amaz.Vector2f(0, 0)
        self.materials:get(0):setFloat("progress", 0)
        self.materials:get(0):setFloat("fade", 0)
        self.materials:get(0):setVec2("trapezoid", Amaz.Vector2f(0, 0))
        -- self.text.verticalPadding = 0
        -- self.text.horizontalPadding = 0
        if not self.first then
            self.text.renderToRT = false
        end
    end
end


function TextAnim:setDuration(duration)
    self.duration = duration
end

function TextAnim:clear()
    Amaz.LOGE("lrc clear", "clear")
    self:resetData()
end


function TextAnim:onEnter()
    Amaz.LOGE("lrc onEnter", "onEnter")
    -- self:resetData()
    self.first = true
end

function TextAnim:onLeave()
    Amaz.LOGE("lrc onLeave", "onLeave")
    self:resetData()
    self.first = true
end

exports.TextAnim = TextAnim
return exports
