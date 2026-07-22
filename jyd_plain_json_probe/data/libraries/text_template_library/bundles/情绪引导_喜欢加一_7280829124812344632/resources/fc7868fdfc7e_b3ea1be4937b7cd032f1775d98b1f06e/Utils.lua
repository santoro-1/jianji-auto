
local Utils = Utils or {}
function Utils.createShaders(vsSrc, psSrc)
    local vs = Amaz.Shader()
    vs.type = Amaz.ShaderType.VERTEX
    vs.source = vsSrc
    local ps = Amaz.Shader()
    ps.type = Amaz.ShaderType.FRAGMENT
    ps.source = psSrc

    local shaders = Amaz.Map()
    local shaderList = Amaz.Vector()
    shaderList:pushBack(vs)
    shaderList:pushBack(ps)
    shaders:insert("gles2", shaderList)
    return shaders
end

function Utils.createPass(shader_vs, shader_fs, renderTexture, blendEnable)
    local renderState = Amaz.RenderState()
    -- renderState.depthstencil = Amaz.DepthStencilState()
    -- renderState.depthstencil.depthTestEnable = false
    -- renderState.depthstencil.depthWriteEnable = false

    renderState.colorBlend = Amaz.ColorBlendState()
    local attachments = Amaz.Vector()
    local attachment = Amaz.ColorBlendAttachmentState()
    attachment.blendEnable = blendEnable
    attachment.srcColorBlendFactor = Amaz.BlendFactor.ONE
    attachment.dstColorBlendFactor = Amaz.BlendFactor.ONE_MINUS_SRC_ALPHA
    attachment.srcAlphaBlendFactor = Amaz.BlendFactor.ONE
    attachment.dstAlphaBlendFactor = Amaz.BlendFactor.ONE_MINUS_SRC_ALPHA
    attachment.colorWriteMask = 15
    attachment.ColorBlendOp = Amaz.BlendOp.ADD
    attachment.AlphaBlendOp = Amaz.BlendOp.ADD
    attachments:pushBack(attachment)
    renderState.colorBlend.attachments = attachments
    local pass = Amaz.Pass()
    pass.shaders = Utils.createShaders(shader_vs, shader_fs)

    pass.clearColor = Amaz.Color(0, 0, 0, 0)
    pass.clearDepth = 1
    pass.clearType = Amaz.CameraClearType.COLOR

    local sem = Amaz.Map()
    sem:insert("position", Amaz.VertexAttribType.POSITION)
    sem:insert("texcoord0", Amaz.VertexAttribType.TEXCOORD0)
    pass.semantics = sem
    pass.useFBOTexture = false
    pass.useCameraRT = false
    pass.renderState = renderState
    if renderTexture then
        pass.renderTexture = renderTexture
    end
    return pass
end

function Utils.createMaterial(material, passes)
    local xshader = Amaz.XShader()
    for i, v in ipairs(passes) do
        xshader.passes:pushBack(v)
    end
    material.xshader = xshader
end

function Utils.CreateRenderTexture(name, width, height, colorFormat)
    local rt = Amaz.ScreenRenderTexture()
    rt.name = name
    rt.builtinType = Amaz.BuiltInTextureType.NORMAL
    rt.internalFormat = Amaz.InternalFormat.RGBA8
    rt.dataType = Amaz.DataType.U8norm
    rt.depth = 1
    rt.attachment = Amaz.RenderTextureAttachment.NONE
    rt.filterMag = Amaz.FilterMode.LINEAR
    rt.filterMin = Amaz.FilterMode.LINEAR
    rt.filterMipmap = Amaz.FilterMipmapMode.FilterMode_NONE
    rt.width = width
    rt.height = height
    rt.colorFormat = colorFormat or Amaz.PixelFormat.RGBA8Unorm
    rt.shared = true
    return rt
end

function Utils.buildRenderChain(comp, renderChain, material)
    local passes = {}
    local colorFormat = Amaz.PixelFormat.RGBA8Unorm
    local RTCounter = {}
    RTCounter[1] = {}
    RTCounter[1].rt = comp.entity.scene:getOutputRenderTexture()
    RTCounter[1].count = 999

    for i = 1, #renderChain do
        if i == #renderChain then
            RTCounter[1].count = 0
        end
        local availableRT = 0
        for j = 1, #RTCounter do
            if RTCounter[j].count == 0 then
                availableRT = j
                break
            end
        end
        if availableRT == 0 then
            availableRT = #RTCounter + 1
            RTCounter[availableRT] = {}
            RTCounter[availableRT].rt = Utils.CreateRenderTexture("tmp_rt_" .. (availableRT - 1), 720, 1280, colorFormat)
            RTCounter[availableRT].count = 0
        end
        renderChain[i].renderTexture = RTCounter[availableRT].rt
        renderChain[i].renderTextureIndex = availableRT
        -- passes[i] = createPass(renderChain[i].shader_vs, renderChain[i].shader_fs,RTCounter[availableRT].rt)
        for j = i + 1, #renderChain do
            for k, v in pairs(renderChain[j].input) do
                if v == renderChain[i].name then
                    RTCounter[availableRT].count = RTCounter[availableRT].count + 1
                end
            end
        end
        for k, v in pairs(renderChain[i].input) do
            for j = i - 1, 1, -1 do
                if renderChain[j].name == v then
                    local m = renderChain[j].renderTextureIndex
                    RTCounter[m].count = RTCounter[m].count - 1
                end
            end
        end
    end

    renderChain[#renderChain].renderTextureIndex = 1
    -- local lastIndex = renderChain[#renderChain].renderTextureIndex
    -- for i = 1, #renderChain do
    --     if renderChain[i].renderTextureIndex == lastIndex then
    --         renderChain[i].renderTextureIndex = 1
    --     elseif renderChain[i].renderTextureIndex == 1 then
    --         renderChain[i].renderTextureIndex = lastIndex
    --     end
    -- end
    for i = 1, #renderChain do
        local availableRT = renderChain[i].renderTextureIndex
        if renderChain[i].renderTextureIndex == 1 then
            passes[i] = Utils.createPass(renderChain[i].shader_vs, renderChain[i].shader_fs, nil, renderChain[i].blendEnable)
        else
            passes[i] =
            Utils.createPass(
                renderChain[i].shader_vs,
                renderChain[i].shader_fs,
                RTCounter[availableRT].rt,
                renderChain[i].blendEnable
            )
        end
    end

    Utils.createMaterial(material, passes)
    for i = 1, #renderChain do
        for k, v in pairs(renderChain[i].input) do
            for j = i - 1, 1, -1 do
                if renderChain[j].name == v then
                    material:setTex(k, RTCounter[renderChain[j].renderTextureIndex].rt)
                end
            end
        end
    end
end
return Utils