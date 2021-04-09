vertex_shader = '''
    uniform mat4 viewProjectionMatrix;
    uniform mat4 worldMatrix;
    uniform float alpha;

    in vec3 position;
    in vec4 color;
    out vec4 fragColor;
   
    void main()
    {
        fragColor = vec4(color.r, color.g, color.b, color.a * alpha);
        gl_Position = viewProjectionMatrix * worldMatrix * vec4(position, 1.0f);
    }
'''

fragment_shader = '''
    in vec4 fragColor;
    
    void main()
    {
        if (fragColor.a == 0) discard;
        gl_FragColor = fragColor;
    }
'''